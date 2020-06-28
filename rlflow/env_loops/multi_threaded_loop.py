from gym.vector import SyncVectorEnv
import numpy as np
from rlflow.data_store.data_store import DataStore, DataManager, DataSaver, BatchStore
from rlflow.selectors.fifo import FifoScheme
import multiprocessing as mp
import queue
from rlflow.adders.logger_adder import LoggerAdder

def run_batch_generator(batch_samples, data_store, batch_generator, term_event):
    while not term_event.is_set():
        try:
            batch_idxs = batch_samples.get_nowait()
        except queue.Empty:
            continue
        batch_generator.store_batch(data_store, batch_idxs)

def run_data_manager(data_manager):
    while True:
        data_manager.update()

def run_actor_loop(actor_fn, n_envs, policy_delayer, vec_env):
    actor = actor_fn()
    dones = np.zeros(n_envs,dtype=np.bool)
    infos = [{} for _ in range(n_envs)]
    obs = vec_env.reset()

    for act_step in range(1000000):
        policy_delayer.actor_step(actor.policy)

        actions = actor.step(obs, dones, infos)

        obs, rews, dones, infos = vec_env.step(actions)
        if act_step % 1000 == 0:
            print("acted")

def noop(x):
    return x

def run_loop(
        logger,
        learner_fn,
        policy_delayer,
        actor_fn,
        environment_fn,
        vec_environment_fn,
        adder_fn,
        adder_wrapper_fn,
        replay_sampler,
        data_store_size,
        batch_size,
        adder_manip=noop,
        ):

    terminate_event = mp.Event()

    example_env = environment_fn()
    example_adder = adder_fn()
    n_envs = 64
    transition_example = example_adder.get_example_output()
    data_store = DataStore(transition_example, data_store_size)
    removal_scheme = FifoScheme()
    empty_entries = mp.Queue(n_envs*2)
    new_entries = mp.Queue(n_envs*2)
    batch_samples = mp.Queue(3)
    data_manager = DataManager(removal_scheme, replay_sampler, data_store_size, empty_entries, new_entries, batch_samples, batch_size)

    env_log_queue = mp.Queue()

    batch_generator = BatchStore(batch_size, transition_example)

    def env_wrap_fn(*args):
        env = environment_fn(*args)
        adder = adder_manip(adder_fn())
        saver = DataSaver(data_store, empty_entries, new_entries)
        adder.set_generate_callback(saver.save_data)
        env = adder_wrapper_fn(env, adder)
        logger_adder = adder_manip(LoggerAdder())
        logger_adder.set_generate_callback(env_log_queue.put)
        env = adder_wrapper_fn(env, logger_adder)
        return env

    vec_env = vec_environment_fn([env_wrap_fn]*n_envs, example_env.observation_space, example_env.action_space)

    mp.Process(target=run_batch_generator,args=(batch_samples, data_store, batch_generator, terminate_event)).start()
    mp.Process(target=run_data_manager,args=(data_manager,)).start()
    mp.Process(target=run_actor_loop,args=(actor_fn, n_envs, policy_delayer, vec_env)).start()

    learner = learner_fn()

    for train_step in range(1000000):
        policy_delayer.learn_step(learner.policy)

        learn_batch = batch_generator.get_batch()
        if learn_batch is None:
            continue
        learner.learn_step(learn_batch)
        batch_generator.batch_copied()

        while not env_log_queue.empty():
            logger.record(*env_log_queue.get_nowait())

        if train_step % 1000 == 0:
            logger.dump()
