import matplotlib.pyplot as plt
from sklearn.decomposition import TruncatedSVD
from sklearn.manifold import TSNE
import numpy as np
from scipy import interpolate


def dim_reduction_plot(data, label):
  
  # PCA
  PCA_model = TruncatedSVD(n_components=3).fit(data)
  data_PCA = PCA_model.transform(data)
  plt.scatter(data_PCA[:,0],data_PCA[:,1],s=60,c=label,marker='.',linewidths = 0,cmap='Paired')
  plt.title('PCA')
  plt.gca().axes.get_xaxis().set_ticks([])
  plt.gca().axes.get_yaxis().set_ticks([])
  plt.show()
  
  # tSNE
#  tSNE_model = TSNE(verbose=2, perplexity=30,min_grad_norm=1E-12,n_iter=3000)
#  data_tsne = tSNE_model.fit_transform(data)
#  plt.scatter(data_tsne[:,0],data_tsne[:,1],c=label,marker='.',linewidths = 0,cmap='Paired')
#  plt.title('tSNE')
#  plt.gca().axes.get_xaxis().set_ticks([])
#  plt.gca().axes.get_yaxis().set_ticks([])
#  plt.show(block=block_flag)
  return


def ideal_kernel(labels):
    K = np.zeros([labels.shape[0], labels.shape[0]])
    
    for i in range(labels.shape[0]):
        k = labels[i] == labels
        k.astype(int)
        K[:,i] = k[:,0]
    return K        
    

def interp_data(X, X_len, restore=False, interp_kind='linear'):
    """data are assumed to be time-major
    interp_kind: can be 'linear', 'nearest', 'zero', 'slinear', 'quadratic', 'cubic'
    """
    
    [T, N, V] = X.shape
    X_new = np.zeros_like(X)
    
    # restore original lengths
    if restore:
        for n in range(N):
            t = np.linspace(start=0, stop=X_len[n], num=T)
            t_new = np.linspace(start=0, stop=X_len[n], num=X_len[n])
            for v in range(V):
                x_n_v = X[:,n,v]
                f = interpolate.interp1d(t, x_n_v, kind=interp_kind)
                X_new[:X_len[n],n,v] = f(t_new)
            
    # interpolate all data to length T    
    else:
        for n in range(N):
            t = np.linspace(start=0, stop=X_len[n], num=X_len[n])
            t_new = np.linspace(start=0, stop=X_len[n], num=T)
            for v in range(V):
                x_n_v = X[:X_len[n],n,v]
                f = interpolate.interp1d(t, x_n_v, kind=interp_kind)
                X_new[:,n,v] = f(t_new)
                
    return X_new


def classify_with_knn(train_data, train_labels, test_data, test_labels, k=3, metric='minkowski'):
    """
    Perform classification with knn.
    """
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.metrics import f1_score
    
    num_classes = len(np.unique(test_labels))

    neigh = KNeighborsClassifier(n_neighbors=k, metric=metric)
    neigh.fit(train_data, train_labels)
    accuracy = neigh.score(test_data, test_labels)
    pred_labels = neigh.predict(test_data)
    if num_classes > 2:
        F1 = f1_score(test_labels, pred_labels, average='weighted')
    else:
        F1 = f1_score(test_labels, pred_labels, average='binary')

    return accuracy, F1

def mse_and_corr(targets, preds, targets_len):
    """
    targets and preds must have shape [time_steps, samples, variables]
    targets_len must have shape [samples,]
    """
    mse_list = []
    corr_list = []
    for i in range(targets.shape[1]):
        len_i = targets_len[i]
        test_data_i = targets[:len_i,i,:]
        pred_i = preds[:len_i,i,:]
        mse_list.append(np.mean((test_data_i-pred_i)**2))
        corr_list.append(np.corrcoef(test_data_i.flatten(), pred_i.flatten())[0,1])
    tot_mse = np.mean(mse_list)
    tot_corr = np.mean(corr_list)
    
    return tot_mse, tot_corr

def anomaly_detect(targets, preds, targets_len, target_labels, threshold=0.5, plot_on=False):
    from sklearn.metrics import f1_score, accuracy_score, roc_auc_score
    
    mse_list = []
    for i in range(targets.shape[1]):
        len_i = targets_len[i]
        test_data_i = targets[:len_i,i,:]
        pred_i = preds[:len_i,i,:]
        err_i = np.mean((test_data_i-pred_i)**2)
        mse_list.append(err_i)
    mean_err = np.mean(mse_list)
    pred_labels = np.where(mse_list >= mean_err*threshold,1,0)
        
    F1 = f1_score(target_labels, pred_labels, average='binary')
    acc = accuracy_score(target_labels, pred_labels)
    auc = roc_auc_score(target_labels, pred_labels)
    print('Anomaly detection -- acc: %.3f, F1: %.3f, AUC: %.3f'%(acc,F1,auc))
    
    if plot_on:
        
        n_class0 = np.sum(target_labels==0)
        n_class1 = np.sum(target_labels==1)
        
        import brewer2mpl
        bmap = brewer2mpl.get_map('Set1', 'qualitative', 3)
        colors = bmap.mpl_colors
        plt.figure(figsize=(5.5,3)) 
        #plt.grid() 
        plt.xlim(1,n_class0+n_class1)
        plt.ylabel('Reconstruction MSE')
        plt.yscale('log')
        plt.title('Outlier detection')        
        plt.bar(np.arange(n_class0), mse_list[:n_class0], color=colors[0], edgecolor='none',width=1.0,label='nominal')
        plt.bar(np.arange(n_class0,len(mse_list)), mse_list[n_class0:], color=colors[1], edgecolor='none',width=1.0,label='outlier') 
        plt.plot([1, n_class0+n_class1], [mean_err*threshold, mean_err*threshold], 'k--', label='threshold', linewidth=2)
        plt.gca().axes.get_xaxis().set_ticks([])
        plt.legend(loc='best', fontsize=10)       
        plt.savefig('../logs/Anomaly_detect.pdf',format='pdf')
        plt.show()
        
    return acc, F1
    

def corr2_coeff(A,B):
    """
    Row-wise mean of input arrays & subtract from input arrays themeselves
    :param A:
    :param B:
    :return:
    """

    A_mA = A - A.mean(1)[:, None]
    B_mB = B - B.mean(1)[:, None]

    # Sum of squares across rows
    ssA = (A_mA**2).sum(1)
    ssB = (B_mB**2).sum(1)

    # Finally get corr coeff
    return np.dot(A_mA, B_mB.T)/np.sqrt(np.dot(ssA[:, None], ssB[None]))

def reverse_input(data, data_len):
    
    data_reversed = np.zeros_like(data)
    for i in range(data_len.shape[0]):
        len_i = data_len[i]
        data_i = data[:len_i,i,:]
        data_reversed[:len_i,i,:] = data_i[::-1,:]
    
    return data_reversed


def check_mso_spectra():
    """
    Debug routing to plot Fourier spectra of 6 randomly selected MSO time series
    with and without interpolation to the maximum time series len.
    """

    from scipy.fftpack import fft
    from TS_datasets import getMSO, getWafer
    from utils import interp_data

    (train_data, train_labels, train_len, _, _,
    _, _, _, _, _,
    _, _, _, _, _) = getMSO(min_len=70, max_len=120)

    train_data_interp = interp_data(train_data, train_len, interp_kind='cubic')

    # select time series and related lengths

    import matplotlib.pyplot as plt

    ts_index_list = np.random.randint(0, 99, 6)
    # multiplot
    plt.figure(1)

    subplot = 231
    for ts_index in ts_index_list:
        ts = train_data[:, ts_index, 0]
        ts_interp = train_data_interp[:, ts_index, 0]
        ts_len = train_len[ts_index]
        ts_interp_len = len(ts_interp)

        # sample spacing
        t = 1.0 / ts_len
        t_interp = 1.0 / ts_interp_len

        # FFT
        y = fft(ts)
        x = np.linspace(0.0, 1.0 / (2.0 * t), ts_len // 2)
        y_interp = fft(ts_interp)
        x_interp = np.linspace(0.0, 1.0 / (2.0 * t_interp), ts_interp_len // 2)

        plt.subplot(subplot)

        plt.plot(x, 2.0 / ts_len * np.abs(y[0:ts_len // 2]), '-b')
        plt.plot(x_interp, 2.0 / ts_interp_len * np.abs(y_interp[0:ts_interp_len // 2]), '-r')
        plt.legend(['original', 'interp'])
        plt.title("Time series ID: " + str(ts_index))
        plt.xlabel('Frequency')
        plt.ylabel('FFT')
        plt.grid()

        subplot += 1

    plt.show()