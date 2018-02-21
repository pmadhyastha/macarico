from __future__ import print_function
from argparse import ArgumentParser
from macarico.annealing import EWMA
from macarico.features.actor import TransitionBOW
from macarico.features.sequence import AttendAt
from macarico.lts.ppo import PPO
from macarico.lts.reinforce import Reinforce
from macarico.policies.linear import LinearPolicy
from macarico.tasks.blackjack import Blackjack
from macarico.tasks.blackjack import BlackjackFeatures
from macarico.tasks.blackjack import BlackjackLoss
from macarico.tasks.cartpole import CartPoleEnv
from macarico.tasks.cartpole import CartPoleFeatures
from macarico.tasks.cartpole import CartPoleLoss
from macarico.tasks.mountain_car import MountainCar
from macarico.tasks.mountain_car import MountainCarFeatures
from macarico.tasks.mountain_car import MountainCarLoss
import dynet as dy
import macarico


def parse_arguments():
    ap = ArgumentParser()
    ap.add_argument('--eps', '-e', default='0.8', type=float,
                    help='epsilon for PPO')
    ap.add_argument('--task', '-t', default='mountaincar', type=str,
                    help='Taks: either cartpole or mountaincar')
    ap.add_argument('--learner', '-l', default='ppo', type=str,
                    help='Learner: either PPO or reinforce')
    ap.add_argument('--dynet-seed', type=int, required=False)
    return ap.parse_args()


def run_trainloop_ppo(ex, actor, loss_fn, eps):
    baseline = EWMA(0.8)
    dy_model = dy.ParameterCollection()
    policy = LinearPolicy(dy_model, actor(dy_model), ex.n_actions)
    optimizer = dy.AdamTrainer(dy_model, alpha=0.01)
    n_actors = 1
    m_batch = 1
    k_epochs = 10
    history, _ = macarico.util.trainloop_ppo(
            training_data      = [ex for i in range(100)],
            n_actors=n_actors,
            m_batch=m_batch,
            k_epochs=k_epochs,
            dev_data           = [ex for i in range(10)],
            policy             = policy,
            Learner            = lambda:PPO(policy, baseline, eps),
            losses             = [loss_fn],
            optimizer          = optimizer,
#            run_per_batch      = run_per_batch + [printit],
            bandit_evaluation  = True,
            dy_model           = dy_model,
            print_dots = False,
            print_freq = 2.0,
#            n_epochs=1,
        )

    return history

def run_ppo(ex, actor, loss_fn, eps):
    print('Eps: ', eps)
    dy_model = dy.ParameterCollection()
    policy = LinearPolicy(dy_model, actor(dy_model), ex.n_actions, n_layers=1, hidden_dim=1)
    baseline = EWMA(0.8)
    optimizer = dy.AdamTrainer(dy_model, alpha=0.01)
    # Total number of iterations
    I = 10000
    # Number of episodes (actors) per iteration is N
    N = 2
    # Number of epochs K
    K = 10
    # Mini-batch size M in multiples of the horizon T  M <= N
    M = 2
    assert(M <= N)
    running_loss = []
    for i in range(I):
        learners_batches = [[]]
        losses_batches = [[]]
        # TODO is this the correct place to implement the renew_cg() func?
        for n in range(N):
            dy.renew_cg()
            learner = PPO(policy, baseline, eps)
            env = ex.mk_env()
            env.run_episode(learner)
            loss = loss_fn(ex, env)
            if len(learners_batches[-1]) == M:
                learners_batches.append([])
                losses_batches.append([])
            learners_batches[-1].append(learner)
            losses_batches[-1].append(loss)
            running_loss.append(loss)
        # For k epochs
        for k in range(K):
            for learner_batch, losses_batch in zip(learners_batches, losses_batches):
                for learner, loss in zip(learner_batch, losses_batch):
                    dy.renew_cg()
                    learner.update(loss)
                optimizer.update()
        print('episode: ', i, 'loss:',
              sum(running_loss[-500:]) / len(running_loss[-500:]))


def test():
    print('')
    print('Proximal Policy Optimization')
    print('')
    args = parse_arguments()
    if args.task == 'mountaincar':
        print('Mountain Car')
        ex = MountainCar()
        run_trainloop_ppo(
            ex,
            lambda dy_model:
            TransitionBOW(dy_model,
                          [MountainCarFeatures()],
                          [AttendAt(lambda _: 0, 'mountain_car')],
                          ex.n_actions),
            MountainCarLoss(),
            args.eps,
        )
    elif args.task == 'cartpole':
        print('Cart Pole')
        ex = CartPoleEnv()
        run_trainloop_ppo(
            ex,
            lambda dy_model:
            TransitionBOW(dy_model,
                          [CartPoleFeatures()],
                          [AttendAt(lambda _: 0, 'cartpole')],
                          ex.n_actions),
            CartPoleLoss(),
            args.eps,
        )
    elif args.task == 'blackjack':
        print('Black Jack')
        ex = Blackjack()
        run_trainloop_ppo(
            ex,
            lambda dy_model:
            TransitionBOW(dy_model,
                          [BlackjackFeatures()],
                          [AttendAt(lambda _: 0, 'blackjack')],
                          ex.n_actions),
            BlackjackLoss(),
            args.eps,
        )
    else:
        print('Unsupported Task!')
        exit(-1)

if __name__ == '__main__':
    test()
