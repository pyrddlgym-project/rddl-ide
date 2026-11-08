from pyRDDLGym_gurobi.core.planner import GurobiOnlineController, load_config_from_string

PARAMETERS = """
    [Gurobi]
    NonConvex=2
    OutputFlag=0

    [Optimizer]
    method='GurobiStraightLinePlan'
    method_kwargs={}
    rollout_horizon=5
    verbose=1
"""

def build_policy(env):
    controller_args = load_config_from_string(PARAMETERS)
    return GurobiOnlineController(rddl=env.model, **controller_args)

def required_env_args():
    return {}
