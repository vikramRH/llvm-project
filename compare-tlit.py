import sys
from rich import print as rp
import argparse
from typing import List, Optional
import subprocess
from rich.live import Live

NPM_TO_LEGACY = {
    "live-debug-values": "livedebugvalues",
    "reg-usage-collector": "RegUsageInfoCollector",
    "prolog-epilog": "prologepilog",
    "lower-invoke": "lowerinvoke",
    "process-imp-defs": "processimpdefs",
    "ee-instrument": "post-inline-ee-instrument"
}

def LEGACY_NAME(npm_passname: str) -> str:
    """
    Convert an npm pass name to its corresponding legacy pass name.
    If the npm pass name is not found in the mapping, return it unchanged.
    """
    return NPM_TO_LEGACY.get(npm_passname, npm_passname)

NOT_MATCH_IN_PASS = [
    "verify",
    "(",
    ")",
    "require<",
    "asm-printer-finalize"
]

def add_stdout_and_enablenpm(cmd: List[str], enable_npm: bool) -> List[str]:
    enpm = "1" if enable_npm else "0"
    return cmd + ['-o', '-', '-enable-new-pm=' + enpm]

def run(cmd):
    output = subprocess.run(cmd, capture_output=True, text=True)
    return output

def prompt_code_diff():
                """Prompt to run the diff command and execute if confirmed."""
                should_run = input("Run the diff command? (y/n): ").strip().lower()
                if should_run == 'y':
                    subprocess.run(["code", "--diff", "npm.out.mir", "legacy.out.mir"])


class CompareRunner:
    """
    Encapsulates the logic for comparing outputs of two passes (legacy and new) for a given test file.
    Handles argument parsing, pass list loading, command extraction, and the main comparison logic.
    """
    def __init__(self):
        self.args = self.parse_args()
        self.pass_list: List[str] = []
        self.run_cmd: List[str] = []

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Compare two files line by line.")
        parser.add_argument("file", type=str, help="Path to the test file")
        parser.add_argument("l", nargs='?', type=str, help="Passname: legacy")
        parser.add_argument("n", type=str, help="Passname: new", nargs="?")
        parser.add_argument("-e", "--auto-explore", action="store_true", help="Automatically explore the test")
        parser.add_argument("--line", type=int, help="The RUN line to run")
        parser.add_argument("--start-before", type=str, help="Start before this pass. Format: <passname>,<instance_num>")
        parser.add_argument("--start-after", type=str, help="Start after this pass." )
        parser.add_argument("--stop-after", type=str, help="Stop after this pass." )
        parser.add_argument("--pass-list", type=str, help="Comma-separated list of passes to run. If not provided, will read from npm-pipeline.log")
        parser.add_argument("-o", "--only-output", action="store_true", help="Only run the command to get the final output before the FileCheck command")
        args = parser.parse_args()
        if args.n is None:
            args.n = args.l
        return args

    def load_pass_list(self, log_file: str = "npm-pipeline.log", ) -> List[str]:
        """Load and process the list of passes from the log file."""
        if self.args.pass_list:
            return self.args.pass_list.split(',')

        with open(log_file, "r") as file:
            lines = file.readlines()
        lines = [line.strip() for line in lines if line.strip()]

        def predicate(line: str) -> bool:
            return not any(not_match in line for not_match in NOT_MATCH_IN_PASS)

        filtered = [line for line in lines if predicate(line)]
        def process(line: str) -> str:
            return line.replace("<", "").replace(">", "").replace(" ", "")
        processed = [process(line) for line in filtered if "verify" not in line]
        if self.args.start_before:
            start_pass, instance_num = self.args.start_before.split(",")
            if start_pass not in processed:
                rp(f"[bold red]Pass '{start_pass}' not found in the pass list![/bold red]")
                sys.exit(1)
            # find the instance_num'th occurrence of start_pass in processed
            instance_num = int(instance_num)
            # using functional programming
            occurrences = [i for i, pass_name in enumerate(processed) if pass_name == start_pass]
            if instance_num > len(occurrences):
                rp(f"[bold red]Instance number {instance_num} for pass '{start_pass}' exceeds the number of occurrences ({len(occurrences)}) in the pass list![/bold red]")
                sys.exit(1)
            start_index = occurrences[instance_num - 1]  # Get the index of the instance_num'th occurrence
            rp(f"[bold green]Starting before pass '{start_pass}' at instance {instance_num} (index {start_index})[/bold green]")
            return processed[start_index:]  # Start after the specified pass
        elif self.args.start_after:
            start_pass, instance_num = self.args.start_after.split(",")
            instance_num = int(instance_num)
            if start_pass not in processed:
                rp(f"[bold red]Pass '{start_pass}' not found in the pass list![/bold red]")
                sys.exit(1)
            occurrences = [i for i, pass_name in enumerate(processed) if pass_name == start_pass]
            if instance_num > len(occurrences):
                rp(f"[bold red]Instance number {instance_num} for pass '{start_pass}' exceeds the number of occurrences ({len(occurrences)}) in the pass list![/bold red]")
                sys.exit(1)
            start_index = occurrences[instance_num - 1]
            return processed[start_index+1:]  # Start at the specified pass
        if self.args.stop_after:
            stop_pass, instance_num = self.args.stop_after.split(",")
            instance_num = int(instance_num)
            if stop_pass not in processed:
                rp(f"[bold red]Pass '{stop_pass}' not found in the pass list![/bold red]")
                sys.exit(1)
            occurrences = [i for i, pass_name in enumerate(processed) if pass_name == stop_pass]
            if instance_num > len(occurrences):
                rp(f"[bold red]Instance number {instance_num} for pass '{stop_pass}' exceeds the number of occurrences ({len(occurrences)}) in the pass list![/bold red]")
                sys.exit(1)
            index = occurrences[instance_num - 1]
            return processed[:index+1]

        return processed[1:]  # skip the first line

    def extract_raw_cmd(self, file: str) -> str:
        filter_out_args = ["-stop-after", "-stop-before", "-enable-new-pm", "-o", "-disable-output"]
        start_of_line = "; RUN:" if file.endswith(".ll") else "# RUN: "
        with open(file, "r") as f:
            for line in f:
                if line.startswith(start_of_line):
                    cmd = line[len(start_of_line):].strip()
                    cmd = cmd.split("|")[0].strip()  # Take the first command before any pipe
                    cmd = cmd.replace("llc", "test_build/bin/llc").replace("%s", "")
                    return cmd
        rp("[bold red]No RUN line found in test.") 
        sys.exit(1)

    def extract_run_cmd(self, file: str) -> List[str]:
        """Extract the run command from the test file's RUN line."""
        filter_out_args = ["-stop-after", "-stop-before", "-enable-new-pm", "-o", "-disable-output"]
        filter_out_args = filter_out_args + ["-" + arg for arg in filter_out_args]
        start_of_line = "; RUN:" if file.endswith(".ll") else "# RUN: "
        with open(file, "r") as f:
            for line in f:
                if line.startswith(start_of_line):
                    cmd = line[len(start_of_line):].strip()
                    cmd = cmd.split("|")[0].strip()  # Take the first command before any pipe
                    cmd = cmd.replace("llc", "test_build/bin/llc").replace("%s", "")
                    # remove any -stop-{after|before}
                    cmd = " ".join([arg for arg in cmd.split() if not any(arg.startswith(filter) for filter in filter_out_args) and arg != '-'])
                    # Remove input redirect if present
                    if "<" in cmd:
                        parts = cmd.split("<")
                        cmd = parts[0] + " ".join(parts[1].split()[1:])
                    cmd = [word for word in cmd.split() if word != '2>&1']  # Remove stderr redirection
                    return cmd
        rp("[bold red]No RUN command found in the file![/bold red]")
        sys.exit(1)

    def run_till_pass(self, passname: str, instance_num: int, live) -> bool:
        """Run the test up to a given pass for both npm and legacy, compare outputs."""
        
        npm_cmd = self.run_cmd + [self.args.file, '-o', '-', f'-stop-after={passname},{instance_num}']
        legacy_cmd = self.run_cmd + [self.args.file, '-o', '-', '-enable-new-pm=0', f'-stop-after={LEGACY_NAME(passname)},{instance_num-1}']
        self.last_npm_cmd = ' '.join(npm_cmd)
        self.last_legacy_cmd = ' '.join(legacy_cmd)
        print("Running commands:")
        live.console.print(f"[dim]NPM cmd: {self.last_npm_cmd}[/dim]")
        live.console.print(f"[yellow]Running for npm: {passname}[/yellow] {self.pass_num}")
        output_npm = run(npm_cmd)
        live.console.print(f"[yellow]Running for legacy: {passname}[/yellow]")
        output_legacy = run(legacy_cmd)
        if output_npm.returncode != 0:
            rp(f"[bold red]NPM pass '{passname}' failed:[/bold red] {output_npm.stderr.strip()}")
            return False
        if output_legacy.returncode != 0:
            rp(f"[bold red]Legacy pass '{passname}' failed.[/bold red]")
            if "pass is not registered" in output_legacy.stderr:
                new_passname = passname.replace("-", "")
                rp(f"\n\t[yellow]Retrying with legacy pass name '{new_passname}'...[/yellow]")
                if new_passname != passname:
                    output_legacy = run(self.run_cmd + [self.args.file, '-o', '-', '-enable-new-pm=0', f'-stop-after={new_passname},{instance_num-1}'])
                if output_legacy.returncode != 0:
                    rp(f"[bold red]Legacy pass '{passname}' failed:[/bold red] {output_legacy.stderr.strip()}")
                    return False
                rp(f"[bold green]Legacy pass '{new_passname}' succeeded![/bold green]")
                return True
            else:
                rp(f"[bold red]Legacy pass '{passname}' failed:[/bold red] {output_legacy.stderr.strip()}")
                return False
        rp(f"Comparing outputs for pass '{passname}'...", end=" ")
        if output_npm.stdout != output_legacy.stdout:
            rp(f"[bold red]Output mismatch for pass '{passname}':[/bold red]")
            with open("npm.out.mir", "w") as f:
                f.write(output_npm.stdout)
            with open("legacy.out.mir", "w") as f:
                f.write(output_legacy.stdout)
            rp("\t[red]Outputs saved to npm.out.mir and legacy.out.mir[/red]")
            return False
        rp(f"[bold green]Outputs match for pass '{passname}'![/bold green]")
        return True

    def get_pass_instance_num(self, passname: str, at_index: int) -> int:
        """Get the instance number of a pass in the pass list.
           This is the count of the number of times this pass appears in the list
           up to the given index (which is this pass's index already).
        """
        assert(self.pass_list[at_index] == passname)
        return sum(1 for i in range(at_index + 1) if self.pass_list[i] == passname)

    def binary_search(self) -> int:
        """Binary search to find the first failing pass."""
        start = 0
        end = len(self.pass_list) - 1
        with Live(f"[bold green]Searching for the first pass that fails...[/bold green]", refresh_per_second=10) as live:
            while start <= end:
                mid = (start + end) // 2
                self.pass_num = mid
                instance_num = self.get_pass_instance_num(self.pass_list[mid], mid)
                live.update(f"[bold green]Searching pass: {self.pass_list[mid]} ({mid}th) ({mid/len(self.pass_list)*100:.2f}%)[/bold green][blue]Range: {start}-{end}[/blue]")
                if self.run_till_pass(self.pass_list[mid], instance_num, live):
                    start = mid + 1
                else:
                    end = mid - 1
            return start

    def auto_explore(self):
        rp(f"[bold green]Auto exploring passes from {self.pass_list[0]} to {self.pass_list[1]}[/bold green]")
        rp(f"[bold green]Total passes: {len(self.pass_list)}[/bold green]")
        index = self.binary_search()
        if index < len(self.pass_list):
            rp(f"[bold blue]Found pass: {self.pass_list[index]}[/bold blue]")
            rp(f"[yellow]{' '.join(self.pass_list[max(0, index-2):index])}[/][bold blue] {self.pass_list[index]}[/] [yellow]{' '.join(self.pass_list[index+1:index+3])}[/]")
            # Print the last cmds run
            rp(f"[bold green]Last NPM command: {self.last_npm_cmd}[/bold green]")
            rp(f"[bold green]Last Legacy command: {self.last_legacy_cmd}[/bold green]")
            rp(f"[blue]See the diff: code --diff npm.out.mir legacy.out.mir[/blue]")
            prompt_code_diff()
        else:
            rp("[bold yellow]All passes succeed, is this the right test?[/bold yellow]")

    def run(self):
        self.pass_list = self.load_pass_list()
        # print(f"Pass list is {self.pass_list}")
        # sys.exit(0)
        self.run_cmd = self.extract_run_cmd(self.args.file)
        if self.args.auto_explore:
            rp(f"[bold green]Run command: {' '.join(self.run_cmd)} {self.args.file} -enable-new-pm=1 -o -[/bold green]")
            self.auto_explore()
        elif self.args.only_output:
            self.run_only_run_command()

    def run_only_run_command(self):
        the_cmd = self.extract_run_cmd(self.args.file)
        npm_cmd = add_stdout_and_enablenpm(the_cmd, True) + [self.args.file]
        leg_cmd = add_stdout_and_enablenpm(the_cmd, False) + [self.args.file]
        rp(f"Command is [blue]{npm_cmd}[/blue]")
        rp(f"Command is [yellow]{leg_cmd}[yellow]")
        npm_out = run(npm_cmd)
        leg_out = run(leg_cmd)
        with open("npm.out.mir", "w") as f:
            f.write(npm_out.stdout)
        with open("legacy.out.mir", "w") as f:
            f.write(leg_out.stdout)
        if npm_out.stdout == leg_out.stdout:
            rp("[bold green]NPM and leg final outputs match.[/bold green]")
        else:
            rp("[bold red]NPM and leg final outputs differ.[/bold red]")
            prompt_code_diff()

    def get_last_cmds(self): 
        """Return the last run commands for npm and legacy."""
        return self.last_npm_cmd, self.last_legacy_cmd


def main():
    runner = CompareRunner()
    runner.run()

if __name__ == "__main__":
    main()
