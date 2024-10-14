# Task03: Loop Invariant Code Motion

CS 265, Chengyi Lux Zhang

link: https://github.com/iansseijelly/bril/tree/main/examples/03-loop

This directory contains a transformation pass for ssa construction and loop analysis. 

## CFG

The CFG is more or less unchaged from last time. I realized that some bril functions call their entry node `entry`, and it made my cfg confused... The solution is to rename my inserted entry node to `sentinel_entry`. 

## SSA

This part took the majority of my time. It is such a pain to implement. `ssa.py` translates the bril program to ssa form. It referred to a lot of construction in `example/to_ssa.py`, like the flow of getting phi -> rename -> insert phi. This makes it very clean and not modify the program until the very last, making iteration easy. I also realized the reference `example/from_ssa.py` does not work out of the box. For many benchmarks it will produce non-existent symbols. For my `from_ssa.py`, I correctly handled all cases by immediately id the results of assignment to a phi argument to the phi destination (in the predecessor block, not the current block), and all benchmarks runs correctly after my ssa passes. (Nothing in brench says "incorrect" at least... A few says "missing" just like the case for HW01 for whatever reason, and when you manually run them it seems ok. Probably the same old regex issue. )

## LICM

My LICM is rather simple. It identify loops via backedges and identifies all invariant loop variables, differentiating the defs from uses. For the defs, it will try to hoist it up to a preheader that's outside the loop if there exists one. 

## Evaluation

[This link](https://docs.google.com/spreadsheets/d/12mtxG8ja89oiqFjuu4fZcAQnq3IsoyqKdS58JzMF3_s/edit?gid=776043870#gid=776043870) is the spreadsheet to the complete results of running brench. 

Among all benchmarks, only `dead-branch` *(-98 dyn insn)* and `pythagorean_triple` *(-7503 dyn insns)* are effectively optimized by my LICM. (Notice that I am comparing `ssa->from_ssa` as the baseline with `ssa->licm->from_ssa` as the optimized version). I have added a remove_nop pass in the very end, because my licm will only mark instructions as nop and not actually remove them. 

This is kind of expected, because I got stucked on loop normalization... And eventually, my LICM specifically looks for patterns like the one in `examples/test/to_ssa/licm.bril`.

```
@main(a: int) {
.while.preheader:
  apple.0: int = const 3;
  orange.0: int = const 5;
.while.cond:
  ...
  banana.1: int = add apple.0 orange.0;
  ...
.while.body:
  ...
.while.finish:
  print a.0;
}
``` 

The `banana.1` assignment should be hoisted up. 
```
@main(a: int) {
.while.preheader:
  apple.0: int = const 3;
  orange.0: int = const 5;
  banana.1: int = add apple.0 orange.0;
.while.cond:
  ...
  banana.1: int = nop apple.0 orange.0;
  ...
.while.body:
  ...
.while.finish:
  print a.0;
}
```
