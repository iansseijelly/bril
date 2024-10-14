import json
import sys

import cfg


def func_from_ssa(func):
    program_cfg, entry_block = cfg.construct_cfg(func["instrs"])

    # Replace each phi-node.
    for block in program_cfg.nodes:
        # Insert copies for each phi.
        for instr in block.instrs:
            if instr.get('op') == 'phi':
                dest = instr['dest']
                type = instr['type']
                for i, label in enumerate(instr['labels']):
                    var = instr['args'][i]
                    if var != "__undefined":
                        # find the block corresponding to the label
                        for p in program_cfg.nodes:
                            if p.label == label:
                                # iterate and find the assign instruction
                                for i, insn in enumerate(p.instrs):
                                    if var in insn.get('dest', []):
                                        p.instrs.insert(i+1, {
                                            'op': 'id',
                                            'type': type,
                                            'args': [var],
                                            'dest': dest,
                                        })
                                        break

        # Remove all phis.
        new_block = [i for i in block.instrs if i.get('op') != 'phi']
        block.instrs = new_block

    func['instrs'] = cfg.cfg_to_instrs(program_cfg)


def from_ssa(bril):
    for func in bril['functions']:
        func_from_ssa(func)
    return bril


if __name__ == '__main__':
    print(json.dumps(from_ssa(json.load(sys.stdin)), indent=2, sort_keys=True))
