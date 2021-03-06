import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime
import itertools
import argparse
import re
import os
import pickle

from sklearn.preprocessing import StandardScaler

from MultiStockEnv import MultiStockEnv
from DQNAgent import DQNAgent


'''
Demo project to trade with AAPL (Apple), MSI (Motorola) and SBUX (Starbucks)
'''

def get_data():
    '''
    Returns
    -------
    T x 3 list of stock prices where each row is a different stock
    0 -> AAPL
    1 -> MSI
    2 -> SBUX
    '''
    # data has only close price information
    df = pd.read_csv('./data/aapl_msi_sbux.csv')
    return df.values


def get_scaler(env):
    # return scikit-learn scaler object to scale the states (we need to play random for this)
    # Note: you could also populate the replay buffer here

    states = []

    for _ in range(env.n_step):
        action = np.random.choice(env.action_space)
        state, reward, done, info = env.step(action)
        states.append(state)

        if done:
            break

    scaler = StandardScaler()
    scaler.fit(states)
    return scaler


def maybe_make_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)



def play_one_episode(agent, env, scaler, is_train):
    # note: after transforming states are already 1xD
    state = env.reset()
    state = scaler.transform([state])
    done = False

    while not done:
        action = agent.act(state)
        next_state, reward, done, info = env.step(action)
        next_state = scaler.transform([next_state])

        if is_train == "train":
            agent.train(state, action, reward, next_state, done)

        state = next_state

    return info['cur_val']


if __name__ == '__main__':

    # config
    models_folder = 'linear_rl_trader_models'
    rewards_folder = 'linear_rl_trader_rewards'

    num_episodes = 2000
    batch_size = 32 # replay memory
    initial_investment = 20000

    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', type=str, required=True, help='either "train" or "test"')
    args = parser.parse_args()

    maybe_make_dir(models_folder)
    maybe_make_dir(rewards_folder)

    data = get_data()
    n_timesteps, n_stocks = data.shape

    n_train = n_timesteps // 2

    train_data = data[:n_train]
    test_data = data[n_train:]

    env = MultiStockEnv(train_data, initial_investment)
    state_size = env.state_dim
    action_size = len(env.action_space)
    agent = DQNAgent(state_size, action_size)
    scaler = get_scaler(env)

    # store the final value of the portfolio (end of episode)
    portfolio_value = []

    if args.mode == 'test':
        # then load the previous scaler
        with open(f'{models_folder}/scaler.pkl', 'rb') as f:
            scaler = pickle.load(f)

        # remake the env with test data
        env = MultiStockEnv(test_data, initial_investment)

        # make sure epsilon is not 1!
        # no need to run multiple episodes if epsilon 0, it is deterministic
        agent.epsilon = 0.01

        # load trained weights
        agent.load(f'{models_folder}/linear.npz')


    # play the game num_episodes times
    for e in range(num_episodes):
        t0 = datetime.now()
        val = play_one_episode(agent,env,scaler,args.mode)
        dt = datetime.now() - t0
        print("episode: {}, episode end value: {:.2f}, duration: {} ".format( (e+1)/num_episodes, val, dt ))
        portfolio_value.append(val) # append episode end portfolio value


    # save the weights when we are done
    if args.mode == 'train':

        # save the DQN
        agent.save(f'{models_folder}/linear.npz')

        # save the scaler
        with open(f'{models_folder}/scaler.pkl', 'wb') as f:
            pickle.dump(scaler, f)

        # plot losses
        plt.plot(agent.model.losses)
        plt.show()

    # save portfolio value for each episode
    np.save(f'{rewards_folder}/{args.mode}.npy', portfolio_value)
