#!/bin/bash
# start queue E on GPU 5 once queue D has finished (keeps <= 6 simulations on the GPU)
D=/home/wangzijun_p25/zhangshuran/core100_inversion; cd $D
while [ ! -f batch1/g0b2D_done.json ]; do sleep 20; done
python3 batch1/refine_queue2.py batch2/g0_plan_E.json 5 g0b2E --max-sims 6 > batch2/g0b2E.log 2>&1
