import jax
import jax.numpy as jnp
import numpy as np
import pettingzoo
from pettingzoo.mpe import simple_world_comm_v2, simple_tag_v2
#from multiagentgymnax.u

from multiagentgymnax.environments.mpe import SimpleTagEnv, SimpleWorldCommEnv

num_episodes, num_steps, tolerance = 10, 25, 1e-4


"""
state = State(
    p_pos=p_pos,
    p_vel=jnp.zeros((self.num_entities, self.dim_p)),
    c=jnp.zeros((self.num_agents, self.dim_c)),
    done=jnp.full((self.num_agents), False),
    step=0
)                        
"""

def np_state_to_jax(env_zoo, env_jax):

    from multiagentgymnax.environments.mpe.mpe_base_env import State

    p_pos = np.zeros((env_jax.num_entities, env_jax.dim_p))
    p_vel = np.zeros((env_jax.num_entities, env_jax.dim_p))
    c = np.zeros((env_jax.num_entities, env_jax.dim_c))
    #print('--', env_zoo.aec_env.agents) # gives list of agent names
    #print('--', env_zoo.aec_env.env.world.agents)
    for agent in env_zoo.aec_env.env.world.agents:
        a_idx = env_jax.a_to_i[agent.name]
        p_pos[a_idx] = agent.state.p_pos
        p_vel[a_idx] = agent.state.p_vel
        c[a_idx] = agent.state.c


    for landmark in env_zoo.aec_env.env.world.landmarks:
        l_idx = env_jax.l_to_i[landmark.name]
        #print('name', landmark.name)
        p_pos[l_idx] = landmark.state.p_pos
        
    #print('p_pos', p_pos)

    state = {
        "p_pos": p_pos,
        "p_vel": p_vel,
        "c": c,
        "step": env_zoo.aec_env.env.steps,
        "done": np.full((env_jax.num_agents), False),
    }
    
    return State(**state)

def assert_same_trans(step, obs_zoo, rew_zoo, done_zoo, obs_jax, rew_jax, done_jax, atol=1e-4):

    for agent in obs_zoo.keys():
        assert np.allclose(obs_zoo[agent], obs_jax[agent], atol=atol), f"Step: {step}, observations for agent {agent} do not match. \nzoo obs: {obs_zoo}, \njax obs: {obs_jax}"
        assert np.allclose(rew_zoo[agent], rew_jax[agent], atol=atol), f"Step: {step}, Reward values for agent {agent} do not match, zoo rew: {rew_zoo[agent]}, jax rew: {rew_jax[agent]}"
        #print('done zoo', done_zoo, 'done jax', done_jax)
        assert np.alltrue(done_zoo[agent] == done_jax[agent]), f"Step: {step}, Done values do not match for agent {agent},  zoo done: {done_zoo[agent]}, jax done: {done_jax[agent]}"

def assert_same_state(env_zoo, env_jax, state_jax, atol=1e-4):

    state_zoo = np_state_to_jax(env_zoo, env_jax)
    
    for k in state_zoo.keys():
        jax_value = getattr(state_jax, k)
        if k not in ["step"]:        
            assert np.allclose(jax_value, state_zoo[k], atol=atol), f"State values do not match for key {k}, zoo value: {state_zoo[k]}, jax value: {jax_value}"


def test_step(zoo_env_name):
    print(f'-- Testing {zoo_env_name} --')
    key = jax.random.PRNGKey(0)
    
    env_zoo, env_jax = env_mapper[zoo_env_name]

    env_zoo = env_zoo.parallel_env(max_cycles=25, continuous_actions=True)
    zoo_obs = env_zoo.reset()
    
    env_jax = env_jax()
    
    env_params = env_jax.default_params
    key, key_reset = jax.random.split(key)
    env_jax.reset(key_reset, env_params)
    for ep in range(num_episodes):
        obs = env_zoo.reset()
        print('\n-- start of loop --')
        for s in range(num_steps):
            actions = {agent: env_zoo.action_space(agent).sample() for agent in env_zoo.agents}
            state = np_state_to_jax(env_zoo, env_jax)
            obs_zoo, rew_zoo, done_zoo, _, _ = env_zoo.step(actions)
            key, key_step = jax.random.split(key)
            obs_jax, state_jax, rew_jax, done_jax, _ = env_jax.step(key_step, state, actions)
            
            assert_same_trans(s, obs_zoo, rew_zoo, done_zoo, obs_jax, rew_jax, done_jax)
            
            if not np.alltrue(done_zoo.values()):
                assert_same_state(env_zoo, env_jax, state_jax)


env_mapper = {
    "simple_world_comm_v2": (simple_world_comm_v2, SimpleWorldCommEnv),
    "simple_tag_v2": (simple_tag_v2, SimpleTagEnv),
}

if __name__=="__main__":

    #test_step("simple_world_comm_v2")
    test_step("simple_tag_v2")