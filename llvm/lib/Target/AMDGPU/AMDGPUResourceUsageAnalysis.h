//===- AMDGPUResourceUsageAnalysis.h ---- analysis of resources -*- C++ -*-===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//
//
/// \file
/// \brief Analyzes how many registers and other resources are used by
/// functions.
///
//===----------------------------------------------------------------------===//

#ifndef LLVM_LIB_TARGET_AMDGPU_AMDGPURESOURCEUSAGEANALYSIS_H
#define LLVM_LIB_TARGET_AMDGPU_AMDGPURESOURCEUSAGEANALYSIS_H

#include "llvm/ADT/SmallVector.h"
#include "llvm/CodeGen/MachineFunctionPass.h"
#include "llvm/IR/PassManager.h"

namespace llvm {

class GCNSubtarget;
class MachineFunction;
class TargetMachine;

struct AMDGPUResourceUsageInfo {
public:
  // Track resource usage for callee functions.
  struct SIFunctionResourceInfo {
    // Track the number of explicitly used VGPRs. Special registers reserved at
    // the end are tracked separately.
    int32_t NumVGPR = 0;
    int32_t NumAGPR = 0;
    int32_t NumExplicitSGPR = 0;
    uint64_t CalleeSegmentSize = 0;
    uint64_t PrivateSegmentSize = 0;
    bool UsesVCC = false;
    bool UsesFlatScratch = false;
    bool HasDynamicallySizedStack = false;
    bool HasRecursion = false;
    bool HasIndirectCall = false;
    SmallVector<const Function *, 16> Callees;
  };

  bool compute(MachineFunction &MF, const TargetMachine& TM);

  const SIFunctionResourceInfo &getResourceInfo() const { return ResourceInfo; }

private:
  SIFunctionResourceInfo
  analyzeResourceUsage(const MachineFunction &MF,
                       uint32_t AssumedStackSizeForDynamicSizeObjects,
                       uint32_t AssumedStackSizeForExternalCall) const;
  SIFunctionResourceInfo ResourceInfo;
};

class AMDGPUResourceUsageWrapperLegacy : public MachineFunctionPass {
  AMDGPUResourceUsageInfo ResourceUsageInfo;
public:
  static char ID;
  
  AMDGPUResourceUsageWrapperLegacy() : MachineFunctionPass(ID) {}

  void getAnalysisUsage(AnalysisUsage &AU) const override {
    AU.setPreservesAll();
    MachineFunctionPass::getAnalysisUsage(AU);
  }
  bool runOnMachineFunction(MachineFunction &MF) override;
  AMDGPUResourceUsageInfo &getInfo() {
    return ResourceUsageInfo;
  }
};

class AMDGPUResourceUsageAnalysis : public AnalysisInfoMixin<AMDGPUResourceUsageAnalysis> {
  friend AnalysisInfoMixin<AMDGPUResourceUsageAnalysis>;
  static AnalysisKey Key;
  const TargetMachine &TM;

public:
  AMDGPUResourceUsageAnalysis(const TargetMachine &TM) : TM(TM) {}

  using Result = AMDGPUResourceUsageInfo;

  Result run(MachineFunction &MF, MachineFunctionAnalysisManager &MFAM) {
    auto Info = AMDGPUResourceUsageInfo();
    Info.compute(MF, TM);
    return Info;
  }
};

} // namespace llvm
#endif // LLVM_LIB_TARGET_AMDGPU_AMDGPURESOURCEUSAGEANALYSIS_H
