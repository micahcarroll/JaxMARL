import jax 
import jax.numpy as jnp
import chex
from typing import Tuple, Dict
from functools import partial
from smax.environments.mpe.simple import SimpleMPE, State
from smax.environments.mpe.default_params import *
from gymnax.environments.spaces import Box

class SimpleSpreadMPE(SimpleMPE):
    
    def __init__(self,
                 num_agents=3,
                 num_landmarks=3,
                 local_ratio=0.5,
                 action_type=DISCRETE_ACT,):
        
        dim_c = 2 # NOTE follows code rather than docs
        
        # Action and observation spaces
        agents = ["agent_{}".format(i) for i in range(num_agents)]
        landmarks = ["landmark {}".format(i) for i in range(num_landmarks)]
        
        observation_spaces = {i: Box(-jnp.inf, jnp.inf, (18,)) for i in agents}
        
        colour = [AGENT_COLOUR] * num_agents + [OBS_COLOUR] * num_landmarks
        
        # Env specific parameters
        self.local_ratio = local_ratio
        assert self.local_ratio >= 0.0 and self.local_ratio <= 1.0, "local_ratio must be between 0.0 and 1.0"
        
        # Parameters
        rad=jnp.concatenate([jnp.full((num_agents), 0.15),
                            jnp.full((num_landmarks), AGENT_RADIUS)])
        
        super().__init__(num_agents=num_agents,
                        agents=agents,
                        num_landmarks=num_landmarks,
                        landmarks=landmarks,
                        action_type=action_type,
                        observation_spaces=observation_spaces,
                        dim_c=dim_c,
                        colour=colour,
                        rad=rad)

    
    def get_obs(self, state: State):

        @partial(jax.vmap, in_axes=(0, None))
        def _common_stats(aidx: int, state: State):
            """ Values needed in all observations """
            
            landmark_pos = state.p_pos[self.num_agents:] - state.p_pos[aidx]  # Landmark positions in agent reference frame

            # Zero out unseen agents with other_mask
            other_pos = (state.p_pos[:self.num_agents] - state.p_pos[aidx]) 
            #other_vel = state.p_vel[:self.num_agents] 
            
            # use jnp.roll to remove ego agent from other_pos and other_vel arrays
            other_pos = jnp.roll(other_pos, shift=self.num_agents-aidx-1, axis=0)[:self.num_agents-1]
            #other_vel = jnp.roll(other_vel, shift=self.num_agents-aidx-1, axis=0)[:self.num_agents-1]
            comm = jnp.roll(state.c[:self.num_agents], shift=self.num_agents-aidx-1, axis=0)[:self.num_agents-1]
            
            other_pos = jnp.roll(other_pos, shift=aidx, axis=0)
            #other_vel = jnp.roll(other_vel, shift=aidx, axis=0)
            comm = jnp.roll(comm, shift=aidx, axis=0)
            
            return landmark_pos, other_pos, comm

        landmark_pos, other_pos, comm = _common_stats(self.agent_range, state)

        def _obs(aidx):
            return jnp.concatenate([
                state.p_vel[aidx].flatten(), # 2
                state.p_pos[aidx].flatten(), # 2
                landmark_pos[aidx].flatten(), # 5, 2
                other_pos[aidx].flatten(), # 5, 2
                comm[aidx].flatten(),
            ])

        obs = {a: _obs(i) for i, a in enumerate(self.agents)}
        return obs
    
    def rewards(self, state: State) -> Dict[str, float]:

        @partial(jax.vmap, in_axes=(0, None, None))
        def _collisions(agent_idx: int, other_idx: int, state: State):
            return jax.vmap(self.is_collision, in_axes=(None, 0, None))(
                agent_idx,
                other_idx,
                state,
            )

        c = _collisions(self.agent_range, 
                        self.agent_range, 
                        state,)  # [agent, agent, collison]

        #jax.debug.print('c {c}', c=c)

        def _good(aidx: int, collisions: chex.Array):

            rew = -1 * jnp.sum(collisions[aidx]) + 1
            #mr = jnp.sum(self.map_bounds_reward(jnp.abs(state.p_pos[aidx])))
            #rew -= mr
            
            return rew 
        
        def _land(land_pos: chex.Array):
            d = state.p_pos[:self.num_agents] -  land_pos
            #jax.debug.print('dists {d}', d=jnp.linalg.norm(d, axis=1))
            return -1 * jnp.min(jnp.linalg.norm(d, axis=1))

        global_rew = jnp.sum(jax.vmap(_land)(state.p_pos[self.num_agents:]))

        rew = {a: _good(i, c) * self.local_ratio + global_rew * (1-self.local_ratio)
               for i, a in enumerate(self.agents)}
        return rew
