import os
import subprocess
from pathlib import Path
from rich import print as rp
from functools import lru_cache
  

def edit_distance1(str1: str, str2: str) -> int:
  """Calculate the Levenshtein distance between two strings."""
  if len(str1) < len(str2):
    str1, str2 = str2, str1
  if len(str2) == 0:
    return len(str1)
  if len(str1) == 0:
    return len(str2)
  cost = 0 if str1[-1] == str2[-1] else 1
  return min(edit_distance(str1[:-1], str2) + 1,
              edit_distance(str1, str2[:-1]) + 1,
              edit_distance(str1[:-1], str2[:-1]) + cost)

def edit_distance(str1, str2):
    """
    Calculate the edit distance between two strings using dynamic programming.

    Args:
        str1 (str): The first string.
        str2 (str): The second string.

    Returns:
        int: The edit distance between the two strings.
    """
    m, n = len(str1), len(str2)

    # Create a DP table to store results of subproblems
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Fill the DP table
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0:
                # If first string is empty, insert all characters of second string
                dp[i][j] = j
            elif j == 0:
                # If second string is empty, remove all characters of first string
                dp[i][j] = i
            elif str1[i - 1] == str2[j - 1]:
                # If last characters are the same, ignore them
                dp[i][j] = dp[i - 1][j - 1]
            else:
                # If last characters are different, consider all possibilities
                dp[i][j] = 1 + min(dp[i - 1][j],    # Remove
                                   dp[i][j - 1],    # Insert
                                   dp[i - 1][j - 1])  # Replace

    return dp[m][n]

def find_files_containing_text(text, directory="llvm", pattern="*.cpp"):
  """Find files containing specific text."""
  matches = []
  for cpp_file in Path(directory).rglob(pattern):
    try:
      with open(cpp_file, encoding="utf-8", errors="ignore") as f:
        if text in f.read():
          matches.append(str(cpp_file))
    except Exception as e:
      print(f"Error reading {cpp_file}: {e}")
  return matches

def beautify_log(message, style="bold green"):
    """Helper function to print styled messages."""
    rp(f"[{style}]{message}[/{style}]")

class PipelineComparer:
  def __init__(self, npm_pipeline, legacy_pipeline):
    self.npm_pipeline = npm_pipeline
    self.legacy_pipeline = legacy_pipeline
    self.only_in_p1 = []
    self.only_in_p2 = []
    self.text_to_file = {}

  def run(self):
    filenames = self.find_source_files_for_passes(self.legacy_pipeline)
    with open("leg-filenames.log", 'w') as f:
      for filename, leg_pass in zip(filenames, self.legacy_pipeline):
        if filename:
          f.write(f"{leg_pass}: {filename}\n")
    npm_class_names = []
    with open("npm-class-names.log", 'w') as f:
      for npm_pass in self.npm_pipeline:
        npm_class_name = self.get_npm_class_name(npm_pass)
        f.write(f"{npm_pass}: {npm_class_name}\n")
        npm_class_names.append(npm_class_name)

    # Now compare the legacy passes with the npm passes in order
    self.compare_pipelines(npm_class_names, self.text_to_file, filenames)
    return

  @lru_cache(maxsize=None)
  def longest_common_subsequence_len(self, i, j):
    if i == -1 or j == -1:
      return 0
    if edit_distance(self.filenames[i], self.npm_class_names[j]) < 5:
      return 1 + self.longest_common_subsequence_len(i - 1, j - 1)
    return max(self.longest_common_subsequence_len(i - 1, j), self.longest_common_subsequence_len(i, j - 1))

  def reconstruct_lcs(self):
    """Reconstruct the longest common subsequence."""
    i, j = len(self.legacy_pipeline) - 1, len(self.npm_pipeline) - 1
    res = {'legacy': [], 'npm': []}
    while i >= 0 and j >= 0:
      if edit_distance(self.filenames[i], self.npm_class_names[j]) < 5:
        res['legacy'].append(i)
        res['npm'].append(j)
        i -= 1
        j -= 1
      elif self.longest_common_subsequence_len(i - 1, j) >= self.longest_common_subsequence_len(i, j - 1):
        i -= 1
      else:
        j -= 1
    # reverse the lists to get them in correct order
    res['legacy'].reverse()
    res['npm'].reverse()
    return res

  def compare_pipelines(self, npm_class_names, _, filenames):
    # Replace None with "None" in npm_class_names
    self.npm_class_names = list(map(lambda x: "None" if x is None else x.replace("Pass", ""), npm_class_names))
    self.filenames = list(map(lambda x: "None" if x is None else x.split('/')[-1].split('.')[0], filenames))
    assert(len(self.npm_pipeline) == len(self.npm_class_names) and "Length mismatch between npm_pipeline and npm_class_names")
    
    beautify_log(f"Legacy Pipeline Length: {len(self.legacy_pipeline)}", style="bold cyan")
    beautify_log(f"NPM Pipeline Length: {len(npm_class_names)}", style="bold cyan")
    beautify_log(f"Longest Common Subsequence Length: {self.longest_common_subsequence_len(len(self.filenames) - 1, len(self.npm_class_names) - 1)}", style="bold cyan")
    beautify_log(f"Reconstructed LCS: {self.reconstruct_lcs()}", style="bold cyan")
    
    self.print_diff(self.reconstruct_lcs())
    return

    # npm_class_names = list(map(lambda x: "None" if x is None else x.replace("Pass", ""), npm_class_names))
    # only_file_names = list(map(lambda x: "None" if x is None else x.split('/')[-1], filenames))
    # print the edit distance between each legacy pass and npm pass
    print(f"{'Legacy Pass':<40} {'NPM Pass Name':<40} {'Edit Distance':<15} {'Source File':<50}")
    for legacy_pass, npm_pass, filename in zip(self.legacy_pipeline, npm_class_names, filenames):
      if not npm_pass:
        continue
      edit_dist = edit_distance(legacy_pass, npm_pass)
      print(f"{legacy_pass:<40} {npm_pass:<40} {edit_dist:<15} {filename:<50}")
  
  def is_analysis(self, passname):
        """Check if the pipeline contains analysis passes."""
        analysis_passes = ["Analysis", "Construction", "Information"]
        return any(ap in passname for ap in analysis_passes)

  def print_diff(self, lcs_res):
        """Write the differences between the legacy and npm pipelines to a file."""
        def write_row(log_file, legacy_pass, npm_pass, source_file):
            """Helper to write a formatted row, splitting long legacy_pass if necessary."""
            if len(legacy_pass) > 50:
                log_file.write(f"{legacy_pass[:48]:<50}\n")
                log_file.write(f"{legacy_pass[48:]:<50} {npm_pass:<40} {source_file:<50}\n")
            else:
                log_file.write(f"{legacy_pass:<50} {npm_pass:<40} {source_file:<50}\n")

        with open("pdiff.log", "w") as log_file:
            log_file.write("\nDifferences between Legacy and NPM Pipelines:\n")
            log_file.write(f"{'Legacy Pass':<50} {'NPM Pass Name':<40} {'Source File':<50}\n")
            log_file.write(f"{'='*50} {'='*40} {'='*50}\n")

            leg_indexes_common = lcs_res['legacy'] + [4000]  # to avoid index out of range
            npm_indexes_common = lcs_res['npm'] + [4000]  # to avoid index out of range
            i, j = 0, 0

            while i < len(self.legacy_pipeline) and j < len(self.npm_pipeline):
                while i < leg_indexes_common[0] and i < len(self.legacy_pipeline):
                    write_row(log_file, self.legacy_pipeline[i], "---====---" if not self.is_analysis(self.legacy_pipeline[i]) else "--ana--", self.filenames[i])
                    i += 1
                while j < npm_indexes_common[0] and j < len(self.npm_class_names):
                    write_row(log_file, "---", self.npm_pipeline[j], self.npm_class_names[j])
                    j += 1
                while i == leg_indexes_common[0] and j == npm_indexes_common[0]:
                    write_row(log_file, self.legacy_pipeline[i], self.npm_pipeline[j], self.filenames[i])
                    i += 1
                    j += 1
                    if len(leg_indexes_common) > 1:
                        leg_indexes_common.pop(0)
                    if len(npm_indexes_common) > 1:
                        npm_indexes_common.pop(0)

  def runold(self):
    # Process legacy pipeline passes
    filenames = self.find_source_files_for_passes(self.legacy_pipeline)
    npm_passes = []
    for npm_pass in self.npm_pipeline:
      npm_pass_name = self.get_npm_class_name(npm_pass)
      if npm_pass_name:
        npm_passes.append(npm_pass_name)
    # Print legacy filename and npm pass name side by side
    print(f"{'Legacy Pass':<40} {'NPM Pass Name':<40} {'Source File':<50}")
    for legacy_file, npm_pass in zip(filenames, npm_passes):
      print(f"{legacy_file:<40} {npm_pass:<40} ")

  def search_pass_in_file(self, filename, pass_name):
      with open(filename, 'r') as f:
        is_next_line_search = False
        for line in f:
          if pass_name in line:
            try:
              class_name = line.split(",")[1].split('(')[0].strip()
              if class_name[-1] == '"' and class_name[0] == '"':
                class_name = class_name[1:-1]
              return class_name
            except Exception as e:
              print(f"Error processing line: {line} -> {e}\n\tMatched: {pass_name}")
      return None

  def get_npm_class_name(self, pass_name: str):
    pass_registry_files = [
      "llvm/lib/Passes/PassRegistry.def",
      "llvm/include/llvm/Passes/MachinePassRegistry.def",
      "llvm/lib/Target/AMDGPU/AMDGPUPassRegistry.def"
    ]

    for filename in pass_registry_files:
      if result := self.search_pass_in_file(filename, pass_name):
        return result
    print(f"Warning: No pass found for {pass_name} in {', '.join(pass_registry_files)}")
    return None
   
  def file_with_text(self, text: str):
    # check the map self.text_to_file first
    if text in self.text_to_file:
      rp(f"Found {text} in cache")
      return self.text_to_file[text]
    # if not found, search in the source files
    matches = find_files_containing_text(text)
    if len(matches) > 1:
      matches = find_files_containing_text(f"\"{text}\"")
    if len(matches) == 1:
      rp(f"File::{matches[0]};;{text}")
      self.text_to_file[text] = matches[0]
      return matches[0]
    # take the filenames for the matches
    filenames = [os.path.basename(m).lower() for m in matches]
    rp(f"Found {len(matches)} matches for {text}: {', '.join(filenames)}")
    distances = [edit_distance(text.lower(), fn) for fn in filenames]
    if distances:
      min_distance = min(distances)
      index = distances.index(min_distance)
      rp(f"Closest match for {text} is {matches[index]} with distance {min_distance}")
      return matches[index]
    rp(f"Warning: No file found for text {text}")
    return None


  def find_source_files_for_passes(self, passes):
    """Find source files containing each pass in the pipeline."""
    self.process_cache_file()
    filenames = []
    for pass_name in passes:
      match = self.file_with_text(pass_name)
      filenames.append(match)
    return filenames
  
  def process_cache_file(self):
    """Parse back the print file from previous runs."""
    filename = "leg-filenames.log"
    if not os.path.exists(filename):
      rp(f"Cache file {filename} does not exist, skipping cache processing.")
      return
    with open(filename, 'r') as f:
      for line in f:
        if ':' in line:
          pass_name, file_path = line.split(':', 1)
          pass_name = pass_name.strip()
          file_path = file_path.strip()
          if pass_name and file_path:
            self.text_to_file[pass_name] = file_path
            rp(f"Cache: {pass_name} -> {file_path}")
        else:
          rp(f"Warning: Line '{line.strip()}' does not contain a valid mapping.")
  
def get_legacy_pipeline(llc_pipeline_file_str: str):
  with open(llc_pipeline_file_str, 'r') as f:
    legacy_pipeline = f.readlines()
  gcn_o2_pipeline = filter(lambda x: x.startswith('; GCN-O2-'), legacy_pipeline)
  filtered_out = filter(lambda x: not "Manager" in x, gcn_o2_pipeline)
  return list(map(lambda x: x.split(':')[1].strip(), filtered_out))

def process_line(nl: str):
  if "(" in nl:
    nl = nl.split('(')[1].strip()
    return process_line(nl)
  # match everything in <...> brackets if present
  # and remove it
  if "<" in nl and ">" in nl:
    nl = nl.split('<')[0].strip() + nl.split('>')[1].strip()
  nl = nl.replace(')', '').strip()
  return nl

def get_npm_pipeline(npm_pipeline_file_str: str):
  with open(npm_pipeline_file_str, 'r') as f:
    npm_pipeline = f.readlines()
  npm_pipeline = list(filter(lambda x: x and "require" not in x, npm_pipeline))
  npm_pipeline = list(map(process_line, npm_pipeline))
  return npm_pipeline

def main():
    llc_pipeline_file_str = 'llvm/test/CodeGen/AMDGPU/llc-pipeline.ll'
    legacy_pipeline = get_legacy_pipeline(llc_pipeline_file_str)
    beautify_log(f"Legacy pipeline passes: {len(legacy_pipeline)}", style="bold cyan")
    npm_pipeline = get_npm_pipeline("npm-pipeline.log")
    beautify_log(f"NPM pipeline passes: {len(npm_pipeline)}", style="bold cyan")
    beautify_log(f"{npm_pipeline}", style="bold cyan")
    comparer = PipelineComparer(npm_pipeline, legacy_pipeline)
    comparer.run()
    beautify_log("Pipeline comparison completed. Check pdiff.log for details.", style="bold green")
    beautify_log("You can also check leg-filenames.log and npm-class-names.log for more details.", style="bold yellow")
    beautify_log("Do not delete the log files after running this script to speed up next invocations.", style="bold yellow")

if __name__ == "__main__":
    main()