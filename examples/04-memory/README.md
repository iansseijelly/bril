# Task04: Memory Optimization

CS 265, Chengyi Lux Zhang

link: https://github.com/iansseijelly/bril/tree/main/examples/04-mem

This directory contains a dead store elimination. 

## dataflow

For dataflow, I used a forward analysis that constructs a "points to" map. Along the way, I also build a store map, and track whether the stores are used before a store at the same location occurs. This is supposed to eliminate any double stores or dead stores, just like a double assignment. 

I came to the realization that for the following code path:
```
  one: int = const 1;
  x: ptr<int> = alloc one;
  store x one;
  x = ptradd x one;
  store x one;
  ret;
```
Is a special case, where even if the point-to map says they are pointing to the same allocation, and the previous store is not used, the previous store should still not be erased, as it might be used in utiilities like packing arguments into arrays. 

One solution is to treat a ptradd as a "use". This matches a programmer intuition where you move the pointer away to no longer point to the previous store, such that the old stores are no longer referenceable, implying that you are not intended to store anything else to the same address perhaps. 

However, that is a very hand-wavy solution. The alternative approach is to apply SSA, and relax this constraint. Now the reassignment will not confuse the point-to map, as the store destination pointers are different. This is the approach I ended up choosing, as it potentially allows for more dead store elimination when there are `ptradds` in the middle. 

## results

It's very sad, but this optimization does not do anything to any of the benchmarks at all... However, I confirmed that it works correctly for all benchmarks (no missing or incorrect), and it eliminate dead stores in my own benchmarks. 

```
(bril) iansseijelly@gym:/scratch/iansseijelly/bril/examples/04-memory$ brench brench_mem.toml 
benchmark,run,result
simple_mem,base,10
simple_mem,memo,9
simple_mem_unrelated,base,14
simple_mem_unrelated,memo,13
simple_mem_used,base,11
simple_mem_used,memo,11
simple_mem_ambiguous,base,12
simple_mem_ambiguous,memo,12
```

Simple_mem contains two consecutive stores, and my pass eliminates it. 
Simple_mem_unrelated contains two stores with an unrelated load in the middle. My pass identifies it is not a use that points to the old dead store, and correctly eliminates the older store. 
Simple_mem_used contains two stores with a directly load in between. My pass identifies it is a use and did not touch it. 
Simple_mem_ambiguous contains two stores with a load from a loaded pointer. My pass identifies id as an `any` reference and does not eliminate the older stores. 

These test cases demonstrate that my passes correctly handle the cases, although very sadly it does not perform anything real in real benchmarks. This implies that real-world workloads probably does not have much dead stores perhaps. 