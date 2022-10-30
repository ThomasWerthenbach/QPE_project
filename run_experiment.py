from plumbum.cmd import minikube, kubectl, helm, docker
from plumbum import local
from itertools import product
from time import sleep

import tomli_w


def gen_job_config():
    epochs = [1]
    std = [10]
    centre = [40]
    values = product(epochs, std, centre)
    names = ["epochs", "std", "centre"]
    return [dict(zip(names, value)) for value in values]


def gen_orch_config():
    sleep = [2.5]
    max_pods_per_node = [3]
    naive = [1, 0]
    values = product(sleep, max_pods_per_node, naive)
    names = ["sleep", "max_pods_per_node", "naive"]
    return [dict(zip(names, value)) for value in values]


def gen_node_config():
    watt_usage = [40]
    watt_delta = [15]
    type_ = ["baremetal"]
    names = ["watt_usage", "watt_delta", "type"]
    values = product(watt_usage, watt_delta, type_)
    return [dict(zip(names, value)) for value in values]


def gen_resize_config():
    std = [10]
    centre = [30]
    values = product(std, centre)
    names = ["std", "centre"]
    return [dict(zip(names, value)) for value in values]


def gen_configs():
    jobs = gen_job_config()
    orchs = gen_orch_config()
    nodes = gen_node_config()
    resizes = gen_resize_config()
    seeds = [42, 41, 40, 39, 38]
    options = product(jobs, orchs, nodes, resizes, seeds)
    names = ["job", "orchestrator", "node", "resize", "seed"]
    return [dict(zip(names, option)) for option in options]


ITERATIONS = 1  # Seeds are included in the configs
DURATION = 1800 + 120  # Time that the experiment is set to + 2 minutes to ensure clean up and other things are finished
INSTALL_CMD = """install experiment-orchestrator charts/orchestrator --namespace test -f charts/fltk-values.yaml --set-file orchestrator.experiment=./configs/distributed_tasks/example_arrival_config.json,orchestrator.configuration=./configs/example_cloud_experiment.json""".split(
    " ")

# FYI:
# THIS EXPERIMENT WILL RUN FOR 5 * 32 * 8 MINUTES = 1280 MINUTES = 21 HOURS
# Thomas: run experiment with lambda set to 0.6 (15 seconds per job arrival)
# Valentijn: run experiments with lambda set to 1.2 (15 seconds per job arrival)

REGISTRY = "gcr.io/qpe-k3z6awuymv44/fltk:latest"

if __name__ == "__main__":
    configs = gen_configs()
    print(f"Total experiments to be ran: {len(configs)}")

    # print(minikube("start", "--driver=podman", "--container-runtime=cri-o"))

    for config in configs:
        for _ in range(ITERATIONS):
            toml_config = tomli_w.dumps(config)
            print("Running the following iteration:\n===========")
            print(toml_config)

            with open("configs/experiment.toml", "wb") as f:
                tomli_w.dump(config, f)

            # Need to be here because we need to push the toml_config
            print("Updating and pushing container")
            with local.env(DOCKER_BUILDKIT="1"):
                print(docker("build", "--platform", "linux/amd64", "-t", REGISTRY, "."))
                print(docker("push", REGISTRY))


            print("Uninstalling experiment-orchestrator")
            try:
                helm("uninstall", "-n", "test", "experiment-orchestrator")
                # Minikube takes some time to terminate pods in some cases
                sleep(60)
            except:
                # Helm uninstall can fail whenever it is not already installed
                # this can safely be ignored
                pass
            print("Reinstalling flearner")
            helm(*INSTALL_CMD)
            print("experiment running")
            sleep(DURATION)
            print("result")
            print(kubectl("logs", "-n", "test", "fl-server"))
            with open("results.txt", "a+") as f:
                f.write(kubectl("logs", "-n", "test", "fl-server"))

    # print(minikube("stop"))

