# vim: fdm=indent
'''
author:     Fabio Zanini
date:       20/05/15
content:    Generic utils for the paper figures.
'''
# Modules
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

fig_width = 5  
fig_fontsize = 12  

def add_panel_label(ax,label, x_offset=-0.1):
    ax.text(x_offset, 0.95, label, transform=ax.transAxes, fontsize=fig_fontsize*1.5)

patients = ['p1', 'p2', 'p3','p5', 'p6', 'p8', 'p9', 'p10', 'p11']
patient_colors = {pcode:col for pcode, col in zip(patients, 
                    sns.color_palette(
                        ['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99',
                         '#e31a1c','#fdbf6f','#ff7f00','#cab2d6'], 
                    n_colors = len(patients)))}

# Functions
def HIVEVO_colormap(kind='website'):
    from scipy.interpolate import interp1d
    maps = {'website': ["#5097BA", "#60AA9E", "#75B681", "#8EBC66", "#AABD52",
                        "#C4B945", "#D9AD3D", "#E59637", "#E67030", "#DF4327"],
            'alternative': ["#A6CEE3", "#1F78B4", "#B2DF8A", "#33A02C", "#FB9A99",
                            "#E31A1C", "#FDBF6F", "#FF7F00", "#CAB2D6", "#6A3D9A"],
           }
    colors = maps[kind]
    rgb_colors = []
    for c in colors:
        rgb_colors.append([int(c[i:i+2],16) for i in [1,3,5]]+[255])
    tmp =interp1d(np.linspace(0,1,len(colors)), np.array(rgb_colors, dtype = float).T/255.0)
    cmap = lambda x: [c for c in tmp(x)]
    return cmap

def add_binned_column(df, bins, to_bin):
    # FIXME: this works, but is a little cryptic
    df.loc[:,to_bin+'_bin'] = np.minimum(len(bins)-2, np.maximum(0,np.searchsorted(bins, df.loc[:,to_bin])-1))

def get_quantiles(q, arr):
    '''
    returns ranges and a boolean index map for each of the q quantiles of array arr 
    as a dict, {i:{'range':(start, stop), 'ind':[True, False, ...]},...}
    '''
    from scipy.stats import scoreatpercentile
    thresholds = [scoreatpercentile(arr, 100.0*i/q) for i in range(q+1)]
    return {i: {'range':(thresholds[i],thresholds[i+1]), 
                'ind':((arr>=thresholds[i])*(arr<thresholds[i+1]))}
           for i in range(q)}

def store_data(data, fn):
    '''Store data to file for the plots'''
    import cPickle as pickle
    with open(fn, 'wb') as f:
        pickle.dump(data, f, protocol=-1)


def load_data(fn):
    '''Load the data for the plots'''
    import cPickle as pickle
    with open(fn, 'rb') as f:
        return pickle.load(f)

def draw_genome(ax, annotations,rows=3, readingframe=True,fs=9):
    from matplotlib.patches import Rectangle
    y1 ,height, pad = 0, 1, 0.2
    ax.set_ylim([-pad,rows*(height+pad)])
    anno_elements = []
    for name, feature in annotations.iteritems():
        x = [feature.location.nofuzzy_start, feature.location.nofuzzy_end]
        anno_elements.append({'name': name,
                     'x1': x[0], 'x2': x[1], 'width': x[1] - x[0]})
    anno_elements.sort(key = lambda x:x['x1'])
    for ai, anno in enumerate(anno_elements):
        if readingframe:
            anno['y1'] = y1 + (height + pad) * (2 - (anno['x1'])%3)
        else:
            anno['y1'] = y1 + (height + pad) * (ai%rows)
        anno['y2'] = anno['y1'] + height

    for anno in anno_elements:
        r = Rectangle((anno['x1'], anno['y1']),
                      anno['width'],
                      height,
                      facecolor=[0.8] * 3,
                      edgecolor='k',
                      label=anno['name'])
        
        xt = anno['x1'] + 0.5 * anno['width']
        yt = anno['y1'] + 0.2 * height + height*(anno['width']<500)

        ax.add_patch(r)
        ax.text(xt, yt,
                anno['name'],
                color='k', 
                fontsize=fs,
                ha='center')

def boot_strap_patients(df, eval_func, columns=None,  n_bootstrap = 100):
    import pandas as pd

    if columns is None:
        columns = df.columns
    if 'pcode' not in columns:
        columns = list(columns)+['pcode']

    patients = df.loc[:,'pcode'].unique()
    tmp_df_grouped = df.loc[:,columns].groupby('pcode')
    npats = len(patients)
    replicates = []
    for i in xrange(n_bootstrap):
        if (i%20==0): print("Bootstrap",i)
        pats = patients[np.random.randint(0,npats, size=npats)]
        bs = []
        for pi,pat in enumerate(pats):
            bs.append(tmp_df_grouped.get_group(pat))
            bs[-1]['pcode']='BS'+str(pi+1)
        bs = pd.concat(bs)
        replicates.append(eval_func(bs))
    return replicates

def replicate_func(reps, col, func, bin_index=None):
    if bin_index is not None:
        nbins = np.max([np.max(d.loc[:,bin_index]) for d in reps])+1
        tmp = np.ma.zeros((len(reps), nbins), dtype = 'float')
        tmp.mask = True
        for ri, rep in enumerate(reps):
            tmp[ri, rep.loc[:,bin_index]] = rep.loc[:,col]
    else:
        tmp = np.ma.array([d.loc[:,col] for d in reps])
    try:
        tmp.mask = np.isnan(tmp) | np.isinf(tmp)
    except:
        print "trouble masking " #,tmp
    return func(tmp, axis=0)


def tree_from_json(json_file):
    '''Convert JSON into a Biopython tree'''
    from Bio import Phylo
    import json
    def node_from_json(json_data, node):
        '''Biopython Clade from json (for recursive call)'''
        for attr,val in json_data.iteritems():
            if attr == 'children':
                for sub_json in val:
                    child = Phylo.BaseTree.Clade()
                    node.clades.append(child)
                    node_from_json(sub_json, child)
            else:
                if attr == 'name':
                    node.__setattr__(attr, str(val))
                    continue

                try:
                    node.__setattr__(attr, float(val))
                except:
                    node.__setattr__(attr, val)

    try:
        with open(json_file, 'r') as infile:
            json_data = json.load(infile)
    except IOError:
        raise IOError("Cannot open "+json_file)

    tree = Phylo.BaseTree.Tree()
    node_from_json(json_data, tree.root)
    tree.root.branch_length=0.01
    return tree


def draw_tree(tree, label_func=str, do_show=True, show_confidence=True,
         # For power users
         x_offset=0, y_offset=0,
         axes=None, branch_labels=None, *args, **kwargs):
    """Plot the given tree using matplotlib (or pylab).

    The graphic is a rooted tree, drawn with roughly the same algorithm as
    draw_ascii.

    Additional keyword arguments passed into this function are used as pyplot
    options. The input format should be in the form of:
    pyplot_option_name=(tuple), pyplot_option_name=(tuple, dict), or
    pyplot_option_name=(dict).

    Example using the pyplot options 'axhspan' and 'axvline':

    >>> Phylo.draw(tree, axhspan=((0.25, 7.75), {'facecolor':'0.5'}),
    ...     axvline={'x':'0', 'ymin':'0', 'ymax':'1'})

    Visual aspects of the plot can also be modified using pyplot's own functions
    and objects (via pylab or matplotlib). In particular, the pyplot.rcParams
    object can be used to scale the font size (rcParams["font.size"]) and line
    width (rcParams["lines.linewidth"]).

    :Parameters:
        label_func : callable
            A function to extract a label from a node. By default this is str(),
            but you can use a different function to select another string
            associated with each node. If this function returns None for a node,
            no label will be shown for that node.
        do_show : bool
            Whether to show() the plot automatically.
        show_confidence : bool
            Whether to display confidence values, if present on the tree.
        axes : matplotlib/pylab axes
            If a valid matplotlib.axes.Axes instance, the phylogram is plotted
            in that Axes. By default (None), a new figure is created.
        branch_labels : dict or callable
            A mapping of each clade to the label that will be shown along the
            branch leading to it. By default this is the confidence value(s) of
            the clade, taken from the ``confidence`` attribute, and can be
            easily toggled off with this function's ``show_confidence`` option.
            But if you would like to alter the formatting of confidence values,
            or label the branches with something other than confidence, then use
            this option.
    """

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        try:
            import pylab as plt
        except ImportError:
            from Bio import MissingPythonDependencyError
            raise MissingPythonDependencyError(
                "Install matplotlib or pylab if you want to use draw.")

    import matplotlib.collections as mpcollections

    # Arrays that store lines for the plot of clades
    horizontal_linecollections = []
    vertical_linecollections = []

    # Options for displaying branch labels / confidence
    def conf2str(conf):
        if int(conf) == conf:
            return str(int(conf))
        return str(conf)
    if not branch_labels:
        if show_confidence:
            def format_branch_label(clade):
                if hasattr(clade, 'confidences'):
                    # phyloXML supports multiple confidences
                    return '/'.join(conf2str(cnf.value)
                                    for cnf in clade.confidences)
                if clade.confidence:
                    return conf2str(clade.confidence)
                return None
        else:
            def format_branch_label(clade):
                return None
    elif isinstance(branch_labels, dict):
        def format_branch_label(clade):
            return branch_labels.get(clade)
    else:
        assert callable(branch_labels), \
            "branch_labels must be either a dict or a callable (function)"
        format_branch_label = branch_labels

    # Layout

    def get_x_positions(tree):
        """Create a mapping of each clade to its horizontal position.

        Dict of {clade: x-coord}
        """
        depths = tree.depths()
        # If there are no branch lengths, assume unit branch lengths
        if not max(depths.values()):
            depths = [x_offset + depth
                      for depth in tree.depths(unit_branch_lengths=True)]
        return depths

    def get_y_positions(tree):
        """Create a mapping of each clade to its vertical position.

        Dict of {clade: y-coord}.
        Coordinates are negative, and integers for tips.
        """
        maxheight = tree.count_terminals()
        # Rows are defined by the tips
        heights = dict((tip, maxheight - i + y_offset)
                       for i, tip in enumerate(reversed(tree.get_terminals())))

        # Internal nodes: place at midpoint of children
        def calc_row(clade):
            for subclade in clade:
                if subclade not in heights:
                    calc_row(subclade)
            # Closure over heights
            heights[clade] = (heights[clade.clades[0]] +
                              heights[clade.clades[-1]]) / 2.0

        if tree.root.clades:
            calc_row(tree.root)
        return heights

    x_posns = get_x_positions(tree)
    y_posns = get_y_positions(tree)
    # The function draw_clade closes over the axes object
    if axes is None:
        fig = plt.figure()
        axes = fig.add_subplot(1, 1, 1)
    elif not isinstance(axes, plt.matplotlib.axes.Axes):
        raise ValueError("Invalid argument for axes: %s" % axes)

    def draw_clade_lines(use_linecollection=False, orientation='horizontal',
                         y_here=0, x_start=0, x_here=0, y_bot=0, y_top=0,
                         color='black', lw='.1'):
        """Create a line with or without a line collection object.

        Graphical formatting of the lines representing clades in the plot can be
        customized by altering this function.
        """
        if (use_linecollection is False and orientation == 'horizontal'):
            axes.hlines(y_here, x_start, x_here, color=color, lw=lw)
        elif (use_linecollection is True and orientation == 'horizontal'):
            horizontal_linecollections.append(mpcollections.LineCollection(
                [[(x_start, y_here), (x_here, y_here)]], color=color, lw=lw),)
        elif (use_linecollection is False and orientation == 'vertical'):
            axes.vlines(x_here, y_bot, y_top, color=color)
        elif (use_linecollection is True and orientation == 'vertical'):
            vertical_linecollections.append(mpcollections.LineCollection(
                [[(x_here, y_bot), (x_here, y_top)]], color=color, lw=lw),)

    def draw_clade(clade, x_start, color, lw):
        """Recursively draw a tree, down from the given clade."""
        x_here = x_posns[clade]
        y_here = y_posns[clade]
        # phyloXML-only graphics annotations
        if hasattr(clade, 'color') and clade.color is not None:
            color = clade.color.to_hex()
        if hasattr(clade, 'width') and clade.width is not None:
            lw = clade.width * plt.rcParams['lines.linewidth']
        # Draw a horizontal line from start to here
        draw_clade_lines(use_linecollection=True, orientation='horizontal',
                         y_here=y_here, x_start=x_start, x_here=x_here, color=color, lw=lw)
        # Add node/taxon labels
        label = label_func(clade)
        if label not in (None, clade.__class__.__name__):
            axes.text(x_here, y_here, ' %s' %
                      label, verticalalignment='center')
        # Add label above the branch (optional)
        conf_label = format_branch_label(clade)
        if conf_label:
            axes.text(0.5 * (x_start + x_here), y_here, conf_label,
                      fontsize='small', horizontalalignment='center')
        if clade.clades:
            # Draw a vertical line connecting all children
            y_top = y_posns[clade.clades[0]]
            y_bot = y_posns[clade.clades[-1]]
            # Only apply widths to horizontal lines, like Archaeopteryx
            draw_clade_lines(use_linecollection=True, orientation='vertical',
                             x_here=x_here, y_bot=y_bot, y_top=y_top, color=color, lw=lw)
            # Draw descendents
            for child in clade:
                draw_clade(child, x_here, color, lw)

    draw_clade(tree.root, 0, 'k', plt.rcParams['lines.linewidth'])

    # If line collections were used to create clade lines, here they are added
    # to the pyplot plot.
    for i in horizontal_linecollections:
        axes.add_collection(i)
    for i in vertical_linecollections:
        axes.add_collection(i)

    # Aesthetics

    if hasattr(tree, 'name') and tree.name:
        axes.set_title(tree.name)
    axes.set_xlabel('branch length')
    axes.set_ylabel('taxa')
    # Add margins around the tree to prevent overlapping the axes
    xmax = max(x_posns.values())
    axes.set_xlim(-0.05 * xmax, 1.25 * xmax)
    # Also invert the y-axis (origin at the top)
    # Add a small vertical margin, but avoid including 0 and N+1 on the y axis
    axes.set_ylim(max(y_posns.values()) + 0.8, 0.2)

    # Parse and process key word arguments as pyplot options
    for key, value in kwargs.items():
        try:
            # Check that the pyplot option input is iterable, as required
            [i for i in value]
        except TypeError:
            raise ValueError('Keyword argument "%s=%s" is not in the format '
                             'pyplot_option_name=(tuple), pyplot_option_name=(tuple, dict),'
                             ' or pyplot_option_name=(dict) '
                             % (key, value))
        if isinstance(value, dict):
            getattr(plt, str(key))(**dict(value))
        elif not (isinstance(value[0], tuple)):
            getattr(plt, str(key))(*value)
        elif (isinstance(value[0], tuple)):
            getattr(plt, str(key))(*value[0], **dict(value[1]))

    if do_show:
        plt.show()

