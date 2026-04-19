from pyRDDLGym_gurobi.core.planner import GurobiStraightLinePlan, GurobiOnlineController

def build_policy(env):
    return GurobiOnlineController(
        rddl=env.model, 
        plan=GurobiStraightLinePlan(), 
        rollout_horizon=5, 
        model_params={'NonConvex': 2, 'OutputFlag': 1}
    )

def required_env_args():
    return {}