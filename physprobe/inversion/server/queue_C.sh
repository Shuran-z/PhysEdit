#!/bin/bash
# Queue C on GPU 2: run_batch-based G0 for T06/T09/T10/T12/T13, then T15 via the original batched physics (one call per task)
D=/home/wangzijun_p25/zhangshuran/core100_inversion; cd $D
python3 batch1/refine_queue2.py batch2/g0_plan_C.json 2 g0b2C --max-sims 6 > batch2/g0b2C.log 2>&1
[ -f G0b2_T15_C01/none_poses.json ] || CUDA_VISIBLE_DEVICES=2 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python batch2/t15_runner.py G0b2_T15_C01 batch2/t15/T15_C01_config.json batch2/t15/T15_C01_physics.json none 0 1 > batch2/G0b2_T15_C01.out 2>&1
[ -f G0b2_T15_C02/none_poses.json ] || CUDA_VISIBLE_DEVICES=2 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python batch2/t15_runner.py G0b2_T15_C02 batch2/t15/T15_C02_config.json batch2/t15/T15_C02_physics.json none 0 1 > batch2/G0b2_T15_C02.out 2>&1
[ -f G0b2_T15_C03/none_poses.json ] || CUDA_VISIBLE_DEVICES=2 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python batch2/t15_runner.py G0b2_T15_C03 batch2/t15/T15_C03_config.json batch2/t15/T15_C03_physics.json none 0 1 > batch2/G0b2_T15_C03.out 2>&1
[ -f G0b2_T15_C04/none_poses.json ] || CUDA_VISIBLE_DEVICES=2 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python batch2/t15_runner.py G0b2_T15_C04 batch2/t15/T15_C04_config.json batch2/t15/T15_C04_physics.json none 0 1 > batch2/G0b2_T15_C04.out 2>&1
[ -f G0b2_T15_C05/none_poses.json ] || CUDA_VISIBLE_DEVICES=2 /home/wangzijun_p25/miniconda3/envs/genesis/bin/python batch2/t15_runner.py G0b2_T15_C05 batch2/t15/T15_C05_config.json batch2/t15/T15_C05_physics.json none 0 1 > batch2/G0b2_T15_C05.out 2>&1
touch batch2/g0b2C_all_done
