import numpy as np
from itertools import izip
from hivevo.patients import Patient
from hivevo.samples import all_fragments

def running_average_masked(obs, ws):
    '''
    calculates a running average
    obs     --  observations
    ws      --  winodw size (number of points to average)
    '''
    try:
        tmp_vals = np.convolve(np.ones(ws, dtype=float), obs*(1-obs.mask), mode='same')
        if len(obs.mask.shape)==0:
            tmp_valid = ws*np.ones_like(tmp_vals)
            # fix the edges. using mode='same' assumes zeros outside the range
            if ws%2==0:
                tmp_vals[:ws//2]*=float(ws)/np.arange(ws//2,ws)
                if ws//2>1:
                    tmp_vals[-ws//2+1:]*=float(ws)/np.arange(ws-1,ws//2,-1.0)
            else:
                tmp_vals[:ws//2]*=float(ws)/np.arange(ws//2+1,ws)
                tmp_vals[-ws//2:]*=float(ws)/np.arange(ws,ws//2,-1.0)
        else:
            tmp_valid = np.convolve(np.ones(ws, dtype=float), (1-obs.mask), mode='same')

        run_avg = np.ma.array(tmp_vals/tmp_valid)
        run_avg.mask = tmp_valid<ws*0.95
    except:
        import pdb; pdb.set_trace()

    return run_avg

def weighted_linear_regression(x,y):
    data = np.array([(tmpx, tmpy) for tmpx, tmpy, m in zip(x,y,y.mask) if not m])
    if len(data)>2:
        weights = data[:,1]+3e-3  #shot noise + sequencing error
        slope = np.sum(data[:,0]*data[:,1]/weights)/np.sum(data[:,0]**2/weights) 
        gof = np.mean((data[:,0]*slope - data[:,1])**2/weights)
        return slope, gof
    else:
        return np.nan, np.nan

if __name__=="__main__":
    import seaborn as sns
    from matplotlib import pyplot as plt
    import argparse
    sns.set_style('whitegrid')

    parser = argparse.ArgumentParser(description="build local tree")
    parser.add_argument('--patients', nargs = '+', help = 'patients to consider')
    params=parser.parse_args()
    plt.ion()

    rate_or_gof = 0
    window_size=300
    cov_min = 200
    HXB2 = -np.ones((len(params.patients), 10000), dtype=float)
    evo_rates = {}
    for pi, pcode in enumerate(params.patients):
        try:
            p = Patient.load(pcode)
        except:
            print "Can't load patient", pcode
        else:
            toHXB2 = p.map_to_external_reference('genomewide')
            aft = p.get_allele_frequency_trajectories('genomewide', cov_min=cov_min)
            aft[aft<0.002]=0
            div_traj = [np.ma.array(af.sum(axis=0) - af[p.initial_indices, np.arange(len(p.initial_indices))], shrink=False) 
                        for af in aft]
            print 'total divergence', zip(p.ysi, [x.sum() for x in div_traj])
            smoothed_divergence = np.ma.array([ running_average_masked(div, window_size) for div in div_traj])
            evo_rates[pcode] =  np.array([weighted_linear_regression(p.ysi, smoothed_divergence[:,i])[rate_or_gof]
                                for i in xrange(smoothed_divergence.shape[1])])
            HXB2[pi,toHXB2[:,0]] = evo_rates[pcode][toHXB2[:,1]]


    ####### plotting ###########
    import seaborn as sns
    from matplotlib import pyplot as plt
    plt.ion()
    sns.set_style('darkgrid')
    figpath = 'figures/'
    fs=16
    fig_size = (5.5, 4.3)

    plt.figure(1,figsize=fig_size)
    HXB2_masked = np.ma.array(HXB2)
    HXB2_masked.mask = HXB2<0
    for pi,pcode in enumerate(params.patients):
        plt.plot(np.arange(HXB2_masked.shape[1])[-HXB2_masked.mask[pi]], 
                 HXB2_masked[pi][-HXB2_masked.mask[pi]], alpha = 0.5, label = pcode)

    plt.plot(np.arange(HXB2_masked.shape[1]), np.exp(np.log(HXB2_masked).mean(axis=0)), c='k', lw=3, label='average')
    plt.xlabel('position [bp]', fontsize=fs)
    plt.ylabel('substitution rate [1/year]', fontsize=fs)
    plt.legend(loc='upper left', ncol=3)
    plt.ylim([2e-4, 6e-2])
    plt.yscale('log')
    for ext in ['pdf','svg', 'png']:
        plt.savefig(figpath+'evolutionary_rates.'+ext)
    print "genome wide variation:", np.std(np.log2(HXB2_masked).mean(axis=0))

    print "position wide variation:", np.mean(np.log2(HXB2_masked+.0001).std(axis=0))