
class GymBaseAdder:
    def get_transition_example(self):
        '''
        returns: list of numpy arrays with the correct shape and dtype of the result
        '''

    def set_generate_callback(self, on_generate):
        '''
        args:
        on_generate: The callback that is called when a new transition is generated
        '''

    def add(self, obs, action, rew, done, info):
        '''
        the observation, reward, done, and info
        generated by the environment
        '''
