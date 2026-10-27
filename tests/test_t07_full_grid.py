from scripts.t07_original_boundary_worker import search_grid


def test_grid_retains_no_flip_without_inventing_boundary():
    grid,intervals=search_grid(lambda x:dict(theta=x,label=0),[.22,.1,.16,.16],.0005)
    assert [r['theta'] for r in grid]==[.1,.16,.22]
    assert intervals==[]


def test_grid_can_find_two_transitions_with_equal_outer_labels():
    def evaluate(x):return dict(theta=x,label=int(.4<=x<=1.6))
    _,intervals=search_grid(evaluate,[0,1,2],.001)
    assert len(intervals)==2
    for interval,expected in zip(intervals,[.4,1.6]):
        a,b=interval['bracket']
        assert a<=expected<=b and b-a<=.001
        assert evaluate(a)['label']!=evaluate(b)['label']
