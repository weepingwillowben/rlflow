from basic_example import FCPolicy, DQNLearner
from rlflow.env_loops.multi_threaded_loop import run_loop
import gym
from rlflow.policy_delayer.occasional_update import OccasionalUpdate
from rlflow.actors.single_agent_actor import StatelessActor
from rlflow.adders import TransitionAdder, AgentAdderConcatter
from rlflow.wrappers.markov_adder_wrapper import MarkovAdderWrapper
from rlflow.selectors import DensitySampleScheme
from rlflow.utils.logger import make_logger
from rlflow.vector import ConcatVecEnv, aec_to_markov, MarkovVectorEnv
from pettingzoo.mpe import simple_world_comm_v0
from supersuit.aec_wrappers import pad_observations, pad_action_space
import copy

def env_fn():
    #env = gym.make("CartPole-v0")#
    env = simple_world_comm_v0.env()
    # print(env.action_spaces.values())
    # exit(0)
    env = pad_observations(env)
    env = pad_action_space(env)
    markov_env = aec_to_markov(env)
    venv = MarkovVectorEnv(markov_env)
    return venv

def adder_wrapper_fn(venv, adder_fn):
    venv.markov_env = MarkovAdderWrapper(venv.markov_env, adder_fn)
    return venv

def main():
    env = env_fn()
    print(env.observation_space)
    obs_size, = env.observation_space.shape
    act_size = env.action_space.n
    device = "cuda"
    policy_fn = lambda: FCPolicy(obs_size, act_size, 64, device)
    data_store_size = 12800
    batch_size = 16
    logger = make_logger("log")
    run_loop(
        logger,
        lambda: DQNLearner(policy_fn(), 0.001, 0.99, logger, device),
        OccasionalUpdate(10, FCPolicy(obs_size, act_size, 64, "cpu")),
        lambda: StatelessActor(policy_fn()),
        env_fn,
        ConcatVecEnv,
        lambda: TransitionAdder(env.observation_space, env.action_space),
        adder_wrapper_fn,
        DensitySampleScheme(data_store_size),
        data_store_size,
        batch_size,
        lambda adder: AgentAdderConcatter(env.markov_env.agents, lambda:copy.deepcopy(adder))
    )
main()
