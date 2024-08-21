
def plot_global_network(central_points, labels, points, output_path):

    fig = plt.figure(figsize=(8,12))

    nodes = []
    pos1, pos2, pos3, pos4, pos5, pos6 = [], [], [], [], [], []
    positions = [pos1, pos2, pos3, pos4, pos5, pos6]

    subs = [321, 322, 323, 324, 325,326]

    ref_r = (6378137.00,6356752.3142)

    m1 = Basemap(projection='npstere',boundinglat=10,lon_0=270,resolution='l')
    m2 = Basemap(projection='geos',lon_0=0,resolution='l',rsphere=ref_r)
    m3 = Basemap(projection='geos',lon_0=90,resolution='l',rsphere=ref_r)
    m4 = Basemap(projection='geos',lon_0=180,resolution='l',rsphere=ref_r)
    m5 = Basemap(projection='geos',lon_0=-90,resolution='l',rsphere=ref_r)
    m6 = Basemap(projection='spstere',boundinglat=-10,lon_0=270,resolution='l')
    projs = [m1,m2,m3,m4,m5,m6]

    t0 = time.time()
    for label in np.unique(qmean.labels_):
        nodes.append(nx.Graph())
        # Select Cluster
        points = np.where(OC[label])[0]
        # Flag centroid point
        remove = np.where(points == central_points[label])[0]
        points = points.tolist()
        # remove centroid point so it's not repeated
        #points.pop(int(remove))
        points.pop(remove[0])
        # add central point to beginning so it's the central connection point
        points.insert(0, central_points[label])
        nx.add_star(nodes[label], points)
        for position, proj in zip(positions, projs):
            mxy = np.zeros_like(LL[points])
            mxy[:,0], mxy[:,1] = proj(LL[points, 0], LL[points,1])
            position.append(dict(zip(nodes[label].nodes, mxy)))

    colors = [plt.cm.prism(each) for each in np.linspace(0, 1, len(nodes))]
    for position, proj, sub in zip(positions, projs, subs):
        fig.add_subplot(sub)
        proj.drawcoastlines()
        proj.fillcontinents(color='grey',lake_color='aqua', alpha=0.3)
        for i, node in enumerate(nodes):
            try:
                # need reshape to squash warning
                r,g,b,a = colors[i]
                nx.draw(node, position[i], node_size=4, alpha=0.95,
                        width=.2, node_color=np.array([r,g,b,a]).reshape(1,4))
            except:
                None

    t1 = time.time()
    fig.supxlabel("Figure runtime:  " + ("%.2fs" % (t1 - t0)).lstrip("0"))
    plt.savefig('/Users/espg/Desktop/testing.png')
