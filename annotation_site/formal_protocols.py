"""Existing T15 contract plus explicit quality-only status for unregistered scenes."""
TARGETS={
 'T01':('the initial book, two cans and mug','初始书本、两只罐子和杯子'),
 'T02':('the initial books, probe and signal object','初始书本、探针及信号物体'),
 'T03':('the initial book, can and foreground objects on the different levels','不同高度处的初始书本、罐子及前景交互物体'),
 'T04':('the initial support book, stacked books and downstream objects','初始支撑书本、堆叠书本及下游物体'),
 'T05':('the initial phone, channel boundaries and can','初始手机、通道边界及罐子'),
 'T06':('the initial sequence of upright books','初始一列直立书本'),
 'T07':('the initial phone, ramp and tabletop','初始手机、斜坡及桌面'),
 'T08':('the initial two books and cup','初始两本书及杯子'),
 'T09':('the initial removable book and stacked objects','初始可抽取书本及堆叠物体'),
 'T10':('the initial tape roll, pen and supported objects','初始胶带卷、笔及被支撑物体'),
 'T11':('the initial eraser, pencil case and eyeglasses case','初始橡皮、笔盒及眼镜盒'),
 'T12':('the initial stapler and tissue box','初始订书机及纸巾盒'),
 'T13':('the initial books and drink carton','初始书本及饮料盒'),
 'T14':('the initial elongated marker, corridor books and downstream objects','初始长笔、构成通道的书本及下游物体'),
 'T15':('the initial green book, closed gray laptop and phone on the floor','初始绿色书本、闭合灰色笔记本电脑及地面手机'),
 'T16':('the initial support object, folder and box','初始支撑物、文件夹及盒子'),
 'T17':('the initial can, ramp and tissue box','初始罐子、斜坡及纸巾盒'),
 'T18':('the initial removable book and stacked books','初始可抽取书本及堆叠书本'),
 'T19':('the initial foreground objects in the collision arrangement','初始碰撞排列中的前景物体'),
 'T20':('the initial book, can, box and cup','初始书本、罐子、盒子及杯子'),
}


def observation_protocol(scene,pilot_t15):
    if scene=='T15':return pilot_t15
    en,zh=TARGETS[scene]
    return {'version':'scene-quality-only-pending-events-v1','status':'diagnostic',
      'scope':'Quality review only. The scene-specific critical event contract is not registered. Do not invent event labels, numeric thresholds or reference outcomes.',
      'critical_contract_status':'pending_scene_specific_registration',
      'target':'追踪'+zh+'。以首帧外观与空间连续性确认身份；不要用后来新出现的同类物体替代。只记录实际画面。',
      'target_en':'Track '+en+' by appearance and spatial continuity from the first frame. Do not substitute new objects for original actors.',
      'events':{}}
