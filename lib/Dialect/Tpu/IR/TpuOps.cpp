//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// TPU-MLIR is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//

#include "tpu_mlir/Support/MathUtils.h"

using namespace tpu_mlir::tpu;

//===----------------------------------------------------------------------===//
// Dialect initialize method.
//===----------------------------------------------------------------------===//
#include "tpu_mlir/Dialect/Tpu/IR/TpuOpsDialect.cpp.inc"

// template <>
// struct FieldParser<AffineExpr> {
//   static FailureOr<AffineExpr> parse(AsmParser &parser) {
//     AffineExpr expr;
//     if (failed(parser.parseAffineExpr({}, expr)))
//       return failure();
//     return expr;
//   }
// };

void TpuDialect::initialize() {
  addOperations<
#define GET_OP_LIST
#include "tpu_mlir/Dialect/Tpu/IR/TpuOps.cpp.inc"
      >();
  addAttributes<
#define GET_ATTRDEF_LIST
#include "tpu_mlir/Dialect/Tpu/IR/TpuAttr.cpp.inc"
      >();
}

//===----------------------------------------------------------------------===//
// Tpu Operator Definitions.
//===----------------------------------------------------------------------===//
#include "tpu_mlir/Dialect/Tpu/IR/TpuEnum.cpp.inc"

#define GET_ATTRDEF_CLASSES
#include "tpu_mlir/Dialect/Tpu/IR/TpuAttr.cpp.inc"

#define GET_OP_CLASSES
#include "tpu_mlir/Dialect/Tpu/IR/TpuOps.cpp.inc"

namespace tpu_mlir {
namespace tpu {
static std::map<Operation *, conv_attr_t> group_conv_attrs;
static std::map<Operation *, pool_attr_t> group_pool_attrs;
static std::map<Operation *, deconv_attr_t> group_deconv_attrs;
static std::map<Operation *, slice_attr_t> group_slice_attrs;

template <typename OpTy, typename AttrTy>
const AttrTy &getOpParam(OpTy &op, std::map<Operation *, AttrTy> &map) {
  auto op_ = op.getOperation();
  auto iter = map.find(op_);
  if (iter != map.end()) {
    return iter->second;
  }
  map[op_] = op.parseParam();
  return map[op_];
}

const conv_attr_t &getConv2DParam(tpu::Conv2DOp &op) {
  return getOpParam<tpu::Conv2DOp, conv_attr_t>(op, group_conv_attrs);
}

const deconv_attr_t &getDeconvParam(tpu::DeconvOp &op) {
  return getOpParam<tpu::DeconvOp, deconv_attr_t>(op, group_deconv_attrs);
}

const pool_attr_t &getPool2DParam(tpu::Pool2DOp &op) {
  return getOpParam<tpu::Pool2DOp, pool_attr_t>(op, group_pool_attrs);
}

const slice_attr_t &getSliceParam(tpu::SliceOp &op) {
  return getOpParam<tpu::SliceOp, slice_attr_t>(op, group_slice_attrs);
}

RunMode getRunMode(FuncOp func) {
  if (func->hasAttr("mode")) {
    return func->getAttrOfType<tpu::RunModeAttr>("mode").getValue();
  }
  return tpu::RunMode::UNKNOW;
}

RunMode getRunMode(Operation *op) {
  FuncOp funcOp;
  if (isa<FuncOp>(op)) {
    funcOp = cast<FuncOp>(op);
  } else if (op->getParentOp()) {
    return getRunMode(op->getParentOp());
  } else {
    llvm_unreachable("top level has no FuncOp!");
  }
  return getRunMode(funcOp);
}

void IfOp::getSuccessorRegions(RegionBranchPoint point,
                               SmallVectorImpl<RegionSuccessor> &regions) {
  // The `then` and the `else` region branch back to the parent operation.
  if (!point.isParent()) {
    regions.push_back(RegionSuccessor(getResults()));
    return;
  }

  regions.push_back(RegionSuccessor(&getThenBranch()));

  // Don't consider the else region if it is empty.
  Region *elseRegion = &this->getElseBranch();
  if (elseRegion->empty())
    regions.push_back(RegionSuccessor());
  else
    regions.push_back(RegionSuccessor(elseRegion));
}

void LoopOp::getSuccessorRegions(RegionBranchPoint point,
                                 SmallVectorImpl<RegionSuccessor> &regions) {
  // If the predecessor is the ForOp, branch into the body using the iterator
  // arguments.
  if (point.isParent()) {
    regions.push_back(RegionSuccessor(&getBody()));
    return;
  }

  // Otherwise, the loop may branch back to itself or the parent operation.
  regions.push_back(RegionSuccessor(&getBody()));
  regions.push_back(RegionSuccessor(getVFinalAndScanOutputs()));
}
} // namespace tpu
} // namespace tpu_mlir
