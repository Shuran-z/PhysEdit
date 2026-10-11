"""CPU PhysX box model for the two-body T12 mechanism; no renderer or target truth."""
import os,sys,json,pathlib,traceback,base64,zlib,math,hashlib
def emit(x):print('__PHYSX_INVERSE__'+json.dumps(x,allow_nan=False),flush=True)
assert not list(pathlib.Path('/dev').glob('nvidia*'))
try:
    request=json.loads(sys.stdin.readline());assert set(request)=={'physics','observation_times_s'}
    observation_times=request['observation_times_s'];assert observation_times[0]==0 and all(math.isfinite(x)and x>=0 for x in observation_times) and all(b>a for a,b in zip(observation_times,observation_times[1:]));p=request['physics'];assert set(p)=={'target','specs','initial','known_gravity','measurement_object','release_direction','unknown_material_roles','physics_dt','steps_per_frame','solver','output_name'}
    assert p['target']in ['gravity','velocity','friction'];assert p['known_gravity']is None if p['target']=='gravity'else p['known_gravity']>0
    if p['target']=='friction':assert all(s['friction']==.1 for s in p['specs']if s['name']in p['unknown_material_roles'])
    if p['target']=='velocity':assert next(i['velocity']for i in p['initial']if i['name']==p['measurement_object'])==p['release_direction']
    assert p['solver']=={'type':'TGS','position_iterations':16,'velocity_iterations':8,'ccd':True}
    assert p['output_name'].replace('_','').isalnum()
    out=pathlib.Path('/work')/p['output_name'];out.mkdir(exist_ok=False);(out/'closed_input.json').write_text(json.dumps(p,indent=2))
    from isaacsim.simulation_app import AppFramework
    app=AppFramework(argv=['--ext-folder','/isaac-sim/extscache','--ext-folder','/isaac-sim/exts','--enable','omni.physx','--/app/extensions/registryEnabled=false','--/renderer/enabled=false','--/app/window/enabled=false','--no-window'])
    import omni.physx,numpy as np
    from pxr import Usd,UsdGeom,UsdPhysics,UsdShade,PhysxSchema,Gf,UsdUtils
    sim=omni.physx.get_physx_simulation_interface();physics=omni.physx.get_physx_interface();cache=UsdUtils.StageCache.Get();names=[s['name']for s in p['specs']if not s['fixed']]
    def run(value):
        stage=Usd.Stage.CreateInMemory();UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z);UsdGeom.SetStageMetersPerUnit(stage,1.)
        scene=UsdPhysics.Scene.Define(stage,'/physicsScene');scene.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1));scene.CreateGravityMagnitudeAttr(value if p['target']=='gravity'else p['known_gravity'])
        options=PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim());options.CreateEnableGPUDynamicsAttr(False);options.CreateBroadphaseTypeAttr('MBP');options.CreateEnableCCDAttr(True);options.CreateSolverTypeAttr('TGS')
        prims=[];initial={i['name']:i for i in p['initial']}
        for s in p['specs']:
            assert set(s)=={'name','size','shape','radius','fixed','mass','friction','restitution','contact_offset','rest_offset'}
            name=s['name'];i=initial[name];root=UsdGeom.Xform.Define(stage,'/World/Event/'+name);q=i['quaternion_xyzw'];xf=UsdGeom.Xformable(root.GetPrim());xf.AddTranslateOp().Set(Gf.Vec3d(*i['position']));xf.AddOrientOp().Set(Gf.Quatf(q[3],Gf.Vec3f(*q[:3])))
            if s['shape']=='sphere':
                proxy=UsdGeom.Sphere.Define(stage,root.GetPath().AppendChild('CollisionProxy'));proxy.CreateRadiusAttr(s['radius'])
            else:
                assert s['shape']=='box';proxy=UsdGeom.Cube.Define(stage,root.GetPath().AppendChild('CollisionProxy'));proxy.CreateSizeAttr(1.);UsdGeom.Xformable(proxy.GetPrim()).AddScaleOp().Set(Gf.Vec3f(*s['size']))
            UsdPhysics.CollisionAPI.Apply(proxy.GetPrim())
            contact=PhysxSchema.PhysxCollisionAPI.Apply(proxy.GetPrim());contact.CreateContactOffsetAttr(s['contact_offset']);contact.CreateRestOffsetAttr(s['rest_offset'])
            mat=UsdShade.Material.Define(stage,'/World/Materials/'+name);mu=value if p['target']=='friction'and name in p['unknown_material_roles']else s['friction'];m=UsdPhysics.MaterialAPI.Apply(mat.GetPrim());m.CreateStaticFrictionAttr(mu);m.CreateDynamicFrictionAttr(mu);m.CreateRestitutionAttr(s['restitution'])
            ma=PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim());ma.CreateFrictionCombineModeAttr('max');ma.CreateRestitutionCombineModeAttr('max');UsdShade.MaterialBindingAPI.Apply(proxy.GetPrim()).Bind(mat,UsdShade.Tokens.weakerThanDescendants,'physics')
            if s['fixed']:continue
            rb=UsdPhysics.RigidBodyAPI.Apply(root.GetPrim());UsdPhysics.MassAPI.Apply(root.GetPrim()).CreateMassAttr(s['mass']);quality=PhysxSchema.PhysxRigidBodyAPI.Apply(root.GetPrim());quality.CreateLinearDampingAttr(0.);quality.CreateAngularDampingAttr(0.);quality.CreateSleepThresholdAttr(0.);quality.CreateEnableCCDAttr(True);quality.CreateSolverPositionIterationCountAttr(16);quality.CreateSolverVelocityIterationCountAttr(8)
            velocity=np.asarray(p['release_direction'])*value if p['target']=='velocity'and name==p['measurement_object']else np.asarray(i['velocity']);rb.CreateVelocityAttr(Gf.Vec3f(*velocity));rb.CreateAngularVelocityAttr(Gf.Vec3f(*[w*180/math.pi for w in i['angular_velocity']]));prims.append(root.GetPrim())
        stage_id=cache.Insert(stage);sim.attach_stage(stage_id.ToLongInt())
        def poses():
            result=[]
            for prim in prims:
                m=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default());q=m.ExtractRotationQuat();result.append([*m.ExtractTranslation(),q.GetReal(),*q.GetImaginary()])
            return result
        h=p['physics_dt'];coordinates=np.asarray(observation_times)/h
        lo=np.floor(coordinates+1e-10).astype(int);hi=np.ceil(coordinates-1e-10).astype(int)
        needed=set(lo)|set(hi);samples={0:np.asarray(poses(),float)}
        for tick in range(1,int(hi.max())+1):
            sim.simulate(h,(tick-1)*h);sim.fetch_results()
            if tick in needed:
                physics.update_transformations(False,True,True,False);samples[tick]=np.asarray(poses(),float)
        rows=[]
        for coordinate,a,b in zip(coordinates,lo,hi):
            if a==b:rows.append(samples[int(a)]);continue
            f=float(coordinate-a);left=samples[int(a)];right=samples[int(b)];value=(1-f)*left+f*right
            for k in range(len(names)):
                qa=left[k,3:]/np.linalg.norm(left[k,3:]);qb=right[k,3:]/np.linalg.norm(right[k,3:]);dot=float(qa@qb)
                if dot<0:qb=-qb;dot=-dot
                if dot>.999999:q=(1-f)*qa+f*qb
                else:
                    angle=np.arccos(np.clip(dot,-1,1));q=(np.sin((1-f)*angle)*qa+np.sin(f*angle)*qb)/np.sin(angle)
                value[k,3:]=q/np.linalg.norm(q)
            rows.append(value)
        sim.detach_stage();cache.Erase(stage_id);a=np.asarray(rows,dtype='<f8');assert np.isfinite(a).all();return a
    probe={'gravity':4.,'velocity':1.,'friction':.5}[p['target']];a=run(probe);run(probe*1.5);b=run(probe);reset=float(np.max(abs(a-b)));assert reset<1e-7
    emit(dict(state='ready',worker_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),CPU_only=True,GPU_devices=[],generated_media=0,solver=p['solver'],reset_cycle_error=reset,body_order=names,model='native_PhysX_condition_box_mechanism',historical_binary_equivalence_claimed=False))
    count=0
    for line in sys.stdin:
        query=json.loads(line)
        if query.get('close'):break
        assert set(query)=={'value'};value=float(query['value']);assert np.isfinite(value)and value>=0;poses=run(value);count+=1
        emit(dict(state='evaluated',value=value,shape=list(poses.shape),poses_f64_zlib_base64=base64.b64encode(zlib.compress(poses.tobytes())).decode()))
        (out/'progress.json').write_text(json.dumps(dict(evaluations=count,last_candidate=value)))
    (out/'completed.json').write_text(json.dumps(dict(evaluations=count,CPU_only=True)));emit(dict(state='closed'));app.close()
except BaseException:
    failure=dict(state='failure',traceback=traceback.format_exc(),no_auto_retry=True,GPU_used=False)
    if'out'in globals():(out/'failure.json').write_text(json.dumps(failure,indent=2))
    emit(failure);raise
