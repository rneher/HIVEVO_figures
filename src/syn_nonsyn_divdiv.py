import argparse
import numpy as np
from itertools import izip
from hivevo.hivevo.patients import Patient
from hivevo.hivevo.samples import all_fragments
from hivevo.hivevo.af_tools import divergence, diversity
from util import store_data, load_data, draw_genome, fig_width, fig_fontsize
import os
from filenames import get_figure_folder


def collect_data_richard(patients, regions, syn_degeneracy=2):
    '''Collect data for divergence and diversity'''

    syn_divergence = {reg:{p:[] for p in patients} for reg in regions} 
    syn_diversity = {reg:{p:[] for p in patients} for reg in regions}
    nonsyn_divergence = {reg:{p:[] for p in patients} for reg in regions}
    nonsyn_diversity = {reg:{p:[] for p in patients} for reg in regions}
    time_bins = np.array([0, 200, 500, 1000, 1500, 2000, 3000, 5000])

    nbins=10
    sfs_tmin=1000
    sfs = {'syn':np.zeros(nbins, dtype=float), 
           'nonsyn':np.zeros(nbins, dtype='float'),
           'bins':np.linspace(0.01,0.99,nbins+1)}
    time_binc = 0.5*(time_bins[1:]+time_bins[:-1])
    cov_min = 100
    for pi, pcode in enumerate(patients):
        try:
            p = Patient.load(pcode)
        except:
            print "Can't load patient", pcode
        else:
            for region in regions:
                for prot in regions[region]:
                    initial_indices = p.get_initial_indices(prot)
                    aft = p.get_allele_frequency_trajectories(prot, cov_min=cov_min)
                    gaps = p.get_gaps_by_codon(prot, pad=2, threshold=0.05)
                    syn_mask = p.get_syn_mutations(prot)
                    syn_pos = (syn_mask.sum(axis=0)>1)*(gaps==False)
                    nonsyn_pos = (syn_mask.sum(axis=0)<=1)*(p.get_constrained(prot)==False)*(gaps==False)
                    print pcode, prot, syn_pos.sum(), nonsyn_pos.sum()
                    syn_divergence[region][pcode].extend([(t, divergence(af[:,syn_pos], 
                                             initial_indices[syn_pos])) for t,af in zip(p.dsi, aft)])
                    syn_diversity[region][pcode].extend([(t, diversity(af[:,syn_pos])) 
                                                        for t,af in zip(p.dsi, aft)])
                    nonsyn_divergence[region][pcode].extend([(t, divergence(af[:,nonsyn_pos], 
                                             initial_indices[nonsyn_pos])) for t,af in zip(p.dsi, aft)])
                    nonsyn_diversity[region][pcode].extend([(t, diversity(af[:,nonsyn_pos])) 
                                                           for t,af in zip(p.dsi, aft)])

                    syn_derived = syn_mask.copy()
                    syn_derived[initial_indices, np.arange(syn_derived.shape[1])]=False
                    for t,af in izip(p.dsi,aft):
                        if t>sfs_tmin:
                            y,x = np.histogram(af[syn_derived].flatten(), bins=sfs['bins'])
                            sfs['syn']+=y
                    nonsyn_derived = syn_mask<=1
                    nonsyn_derived*=(p.get_constrained(prot)==False)*(gaps==False)
                    nonsyn_derived[initial_indices, np.arange(syn_derived.shape[1])]=False
                    for t,af in izip(p.dsi,aft):
                        if t>sfs_tmin:
                            y,x = np.histogram(af[nonsyn_derived], bins=sfs['bins'])
                            sfs['nonsyn']+=y

    for tmp_data in [syn_divergence, syn_diversity, nonsyn_diversity, nonsyn_divergence]:
        for region in regions:
            tmp = np.vstack([np.array(tmp_data[region][p]) for p in patients])
            tmp_clean = tmp[-np.isnan(tmp[:,1]),:]
            y,  x = np.histogram(tmp_clean[:,0],bins = time_bins, weights = tmp_clean[:,1])
            yn, x = np.histogram(tmp_clean[:,0],bins = time_bins)
            tmp_data[region] = {'avg':y/(1e-10+yn), 'bins':time_binc, 'raw':tmp_data[region]}

    data = {'syn_diversity':syn_diversity, 'syn_divergence':syn_divergence,
            'nonsyn_diversity':nonsyn_diversity, 'nonsyn_divergence':nonsyn_divergence,
            'sfs':sfs}

    return data


def collect_data_fabio(patients, regions, cov_min=100, syn_degeneracy=2):
    '''Collect data for divergence and diversity'''
    import pandas as pd
    from itertools import izip

    # Prepare SFS
    nbins=10
    sfs_tmin=1000
    sfs = {'syn': np.zeros(nbins, dtype=float), 
           'nonsyn': np.zeros(nbins, dtype=float),
           'bins': np.linspace(0.01, 0.99, nbins+1),
          }

    # Collect into DataFrame
    data = []
    for pi, pcode in enumerate(patients):
        p = Patient.load(pcode)
        for region, prots in regions.iteritems():
            for prot in prots:
                aft = p.get_allele_frequency_trajectories(prot, cov_min=cov_min)
                initial_indices = p.get_initial_indices(prot)
                gaps = p.get_gaps_by_codon(prot, pad=2, threshold=0.05)

                # Classify syn/nonsyn POSITIONS
                # NOTE: this is not fully correct because some positions (2-fold
                # degenerate) are both syn and nonsyn, but it's close enough
                syn_mask = p.get_syn_mutations(prot)
                syn_sum = syn_mask.sum(axis=0)
                # NOTE: syn_mask == 0 are substitutions, they make up most
                # of the nonsynonymous signal
                pos = {'syn': (syn_sum >= syn_degeneracy) & (-gaps),
                       'nonsyn': (syn_sum <= 1) & (-p.get_constrained(prot)) & (-gaps),
                      }
                
                print pcode, prot, pos['syn'].sum(), pos['nonsyn'].sum()

                # Divergence/diversity
                for t, af in izip(p.dsi, aft):
                    for mutclass, ind in pos.iteritems():
                        data.append({'pcode': pcode,
                                     'time': t,
                                     'region': region,
                                     'protein': prot,
                                     'nsites': ind.sum(),
                                     'mutclass': mutclass,
                                     'divergence': divergence(af[:, ind], initial_indices[ind]),
                                     'diversity': diversity(af[:, ind]),
                                    })


                # Site frequency spectrum
                syn_derived = syn_mask.copy()
                syn_derived[initial_indices, np.arange(syn_derived.shape[1])] = False
                nonsyn_derived = (-syn_mask) & (-p.get_constrained(prot)) & (-gaps)
                nonsyn_derived[initial_indices, np.arange(syn_derived.shape[1])] = False

                for t,af in izip(p.dsi,aft):
                    if t < sfs_tmin:
                        continue

                    sfs['syn'] += np.histogram(af[syn_derived], bins=sfs['bins'])[0]
                    sfs['nonsyn'] += np.histogram(af[nonsyn_derived], bins=sfs['bins'])[0]


    data = pd.DataFrame(data)
    data['divergence'] = data['divergence'].astype(float)
    data['diversity'] = data['diversity'].astype(float)

    # Make time bins
    time_bins = np.array([0, 200, 500, 1000, 1500, 2000, 3000, 5000])
    time_binc = 0.5 * (time_bins[1:] + time_bins[:-1])
    from hivwholeseq.utils.pandas import add_binned_column
    add_binned_column(data, 'tbin', 'time', bins=time_bins, clip=True)
    data['tbinc'] = time_binc[data['tbin']]

    # Average over patients
    datap = (data
             .loc[:, ['mutclass', 'tbinc', 'region', 'divergence', 'diversity']]
             .groupby(['mutclass', 'region', 'tbinc'])
             .mean())

    # Put it into a data structure that the plot function understands
    # NOTE: this is here for compatibility with Richard
    dataf = {}
    for mutclass in ['syn', 'nonsyn']:
        for obs in ['diversity', 'divergence']:
            datum = datap[obs].unstack('tbinc').loc[mutclass]
            d = {name: {'bins': np.array(_.index), 'avg': np.array(_)}
                 for name, _ in datum.iterrows()}
            dataf[mutclass+'_'+obs] = d

    dataf['sfs'] = sfs

    return dataf


def plot_divdiv(data, fig_filename=None, figtypes=['.png', '.svg', '.pdf']):
    ####### plotting ###########
    import seaborn as sns
    from matplotlib import pyplot as plt
    plt.ion()
    sns.set_style('darkgrid')
    figpath = 'figures/'
    fs=fig_fontsize
    fig_size = (4.0/3*fig_width, 0.66*fig_width)

    fig, axs = plt.subplots(1, 2, sharey=True,figsize=fig_size)
    ax=axs[0]
    colors = {reg:c for reg, c in zip(data['syn_divergence'].keys(), 
                                      sns.color_palette(n_colors=4))}
    for region, d in data['nonsyn_divergence'].iteritems():
        ax.plot(d['bins'], d['avg'], ls='-', c=colors[region], lw=3, label=region)
    for region, d in data['nonsyn_diversity'].iteritems():
        ax.plot(d['bins'], d['avg'], ls='--', c=colors[region], lw=3, label=None)
    ax.legend(loc=2, fontsize=fs)
    ax.set_xticks([0,1000,2000,3000])
    for item in ax.get_yticklabels()+ax.get_xticklabels():
        item.set_fontsize(fs)
    ax.set_xlabel('EDI [days]', fontsize=fs)
    ax.set_ylabel('divergence/diversity', fontsize=fs)

    ax=axs[1]
    for region, d in data['syn_divergence'].iteritems():
        ax.plot(d['bins'], d['avg'], ls='-',c=colors[region], lw=3,
                label=('divergence' if region=='enzymes' else None))
    for region, d in data['syn_diversity'].iteritems():
        ax.plot(d['bins'], d['avg'], ls='--',c=colors[region], lw=3,
                label=('diversity' if region=='enzymes' else None))

    ax.legend(loc=2, fontsize=fs)
    for item in ax.get_yticklabels()+ax.get_xticklabels():
        item.set_fontsize(fs)
    ax.set_xticks([0,1000,2000,3000])
    ax.set_xlabel('EDI [days]', fontsize=fs)
    plt.tight_layout(rect=(0.0, 0.02, 0.98, 0.98), pad=0.05, h_pad=0.5, w_pad=0.4)

    if fig_filename is not None:
        for ext in figtypes:
            #fig.savefig(fig_filename+ext)
            pass
    else:
        plt.ion()
        plt.show()

    ########## sfs ##############
    sfs=data['sfs']
    fig_size = (2.0/3*fig_width, 0.66*fig_width)
    fig = plt.figure(figsize=fig_size)
    ax=plt.subplot(111)
    colors = sns.color_palette(n_colors=2)
    binc = binc = 0.5*(sfs['bins'][1:]+sfs['bins'][:-1])
    ax.bar(binc-0.045, sfs['syn']/np.sum(sfs['syn']),width = 0.04, label='synonymous', color=colors[0])
    ax.bar(binc, sfs['nonsyn']/np.sum(sfs['nonsyn']),width = 0.04, label='nonsynonymous', color=colors[1])
    ax.set_yscale('log')
    ax.set_xlabel('frequency',fontsize=fs)
    ax.set_ylabel('fractions of SNVs',fontsize=fs)
    ax.legend(loc=1, fontsize=fs)
    ax.set_ylim([0.005,1.1])
    for item in ax.get_yticklabels()+ax.get_xticklabels():
        item.set_fontsize(fs)
    plt.tight_layout(rect=(0.0, 0.02, 0.98, 0.98), pad=0.05, h_pad=0.5, w_pad=0.4)

    if fig_filename is not None:
        for ext in figtypes:
            #fig.savefig(fig_filename+'_sfs'+ext)
            pass
    else:
        plt.ion()
        plt.show()



if __name__=="__main__":

    parser = argparse.ArgumentParser(description="Make figure for divergence and diversity")
    parser.add_argument('--redo', action='store_true', help='recalculate data')
    params = parser.parse_args()

    username = os.path.split(os.getenv('HOME'))[-1]
    foldername = get_figure_folder(username, 'first')
    fn_data = foldername+'data/'
    fn_data = fn_data + 'syn_nonsyn_divergence.pickle'

    if not os.path.isfile(fn_data) or params.redo:
        patients = ['p1', 'p2', 'p3','p5', 'p6', 'p8', 'p9', 'p10','p11']
        regions = {'structural':['gag'], #['p17', 'p24'],
                    'enzymes':  ['pol'], #['PR', 'RT', 'p15', 'IN'],
                    'accessory': ['vif', 'nef', 'vpr', 'vpu', 'tat', 'rev'],
                    'envelope': ['env'] #['gp41', 'gp120'],
                    }
        # NOTE: these two give the same result, good
        data = collect_data_fabio(patients, regions)
        #data = collect_data_richard(patients, regions)
        store_data(data, fn_data)
    else:
        print("Loading data from file")
        data = load_data(fn_data)

    plot_divdiv(data, fig_filename = foldername+'divdiv')
