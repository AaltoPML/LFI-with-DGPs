# Likelihood-free Inference with Deep Gaussian Processes

This folder contains all the code required to replicate experiments described in the paper. The simulator that are used in this project are
implemented on top of the Engine for Likelihood-free Inference (ELFI).

## Getting Started

The project dependencies can be installed with conda by using the following command in the directory of the project (Python 3.7 version is required):

```
conda create --name lfidgp --file requirements.txt
conda activate lfidgp
pip install --user -e elfidev/
```
An additional installation of the following packages may be necessary:
```
pip install gpflow==1.5.0 tensorflow-probability==0.7.0 tensorflow==1.14.0 seaborn simple-rl
pip install git+https://github.com/justinalsing/pydelfi.git
```

## Preparing the experiments

Before running the LFI experiments, the ground truth values must be calculated for the given simulator (TE1 in the examples below). First one needs to run 10^7 simulations (this will take a couple of days for the BDM and NW simulators, so parallelization is highly recommended):
```
python run_experiment.py --meth=Rej --sim=TE1 --evidence=10000000 --seed=0
```
Followed by creating the true posterior by leaving 1000 simulations with the lowest discrepancy:
```
python run_experiment.py --meth=True --sim=TE1 --evidence=1000 --seed=0
```
This will create the ground-truth posterior, which will be used when calculating the Wasserstein distance, for LFI experiments. It will be stored in the 'results/TE1/True' folder.


## Running the LFI experiments

All experiments can be run through 'run_experiment.py' and passing the correct arguments. Specifically, to run one of the models, specify the method (BO, NDE or KELFI), the surrogate model (GP, DGP, MDN, MAF), the simulator (TE1, TE2, TE3, TE4, BDM, CI, SL, NW), the random seed of the experiments, and the evidence (i.e. the number of simulations to run). For instance:
```
python run_experiment.py --meth=BO --surrogate=GP --sim=TE1 --seed=0 --evidence=200
```
will run BOLFI with the standard GP for the TE1 simulator with 200 simualations. The results will be saved in the 'results/TE1/BO-GP(200)' folder. Note, that KELFI does not have a surrogate, and DGPs have additional parameters:
the number of GP and LV layers, and the quantile threshold value. For instance:
```
python run_experiment.py --meth=BO --surrogate=DGP --sim=NW --seed=0 --evidence=200 --gplayers=2 --lv=True --q=0.3
```
will run the LV-2GP variant of the DGP for the NW simulatior with 200 simulations and with the quantile threshold equal to 0.3. The results will be stored in the 'results/NW/BO-LV-2GP-0.3(200)' folder.


## Collecting the results

Once the experiments have run, the results can be retrieved. The most easiest way to collect them is by simply running 
```
python run_experiment.py --meth=Tex --seed=0
```
which will print the Wasserstein distance (the mean and std) in Latex format for all available experiments. 

It is also possible to plot the marginals of the target posteriors for LV-2GP and GP with:
```
python run_experiment.py --meth=MargPlot --sim=TE1 --seed=0
```
and the Wasserstein distance boxplots (which will go through all experiments):
```
python run_experiment.py --meth=WassPlot --seed=0
```
the plots are stored in the 'plots/' folder.

## Citation

```
@article{aushev2022likelihood,
  title={Likelihood-free inference with deep Gaussian processes},
  author={Aushev, Alexander and Pesonen, Henri and Heinonen, Markus and Corander, Jukka and Kaski, Samuel},
  journal={Computational Statistics \& Data Analysis},
  volume={174},
  pages={107529},
  year={2022},
  publisher={Elsevier}
}
```

Full article: https://www.sciencedirect.com/science/article/pii/S0167947322001098
