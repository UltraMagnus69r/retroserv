"""Replay the boot-to-level input sequence and save the reference frame."""
from capture import run, snapshot, status
run(135); run(1,3); run(180)
run(1,8); run(85)
run(1,8); run(360)
run(1,8); run(135)
run(1,6); run(60)
run(1,8); run(370); snapshot('intro_actual')
for key in (3,0,8,2,1):
 run(2,key);run(90);snapshot('key'+str(key))
run(1,8); run(190); snapshot('overworld_actual')
run(1,6); run(85); snapshot('node_actual')
run(1,8); run(118); snapshot('opening')
run(200);snapshot('overworld2')
run(1,6);run(90);snapshot('left2')
run(1,8);run(125);snapshot('opening2')
run(40);snapshot('opening3')
run(35);snapshot('opening4')
assert status()[:3] == (0x14, 0x29, 1), 'Expected active gameplay in Yoshi’s Island 1'
