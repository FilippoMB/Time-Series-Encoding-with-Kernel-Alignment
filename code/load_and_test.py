import tensorflow as tf
import matplotlib.pyplot as plt
from TS_datasets import *
from utils import dim_reduction_plot, mse_and_corr, classify_with_knn
import numpy as np
import argparse, sys

# parse input data
parser = argparse.ArgumentParser()
parser.add_argument("--dataset_id", default='BLOOD', help="ID of the dataset", type=str)
parser.add_argument("--graph_name", default="20171109-000147", help="name of the file to be loaded", type=str)
parser.add_argument("--dim_red", dest='dim_red', action='store_true', help="compute PCA and tSNE")
parser.add_argument("--plot_on", dest='plot_on', action='store_true', help="make plots")
parser.add_argument("--plot_code", dest='plot_code', action='store_true', help="plots the code in 2d")
parser.set_defaults(dim_red=True)
parser.set_defaults(plot_on=True)
parser.set_defaults(plot_code=False)
args = parser.parse_args()

# ================= LOAD DATA ===================

if args.dataset_id == 'SYNTH':
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getSynthData(name='Lorentz', 
                                                                tr_data_samples=200, 
                                                                vs_data_samples=200, 
                                                                ts_data_samples=2000)
elif args.dataset_id == 'ECG':
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getECGData()
       
elif args.dataset_id == 'JAP':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getJapDataFull()

elif args.dataset_id == 'JAPm':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getJapDataMiss(kernel='TCK', inp='zero', miss=0.5)
   
elif args.dataset_id == 'LIB':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getLibras()
    
elif args.dataset_id == 'CHAR':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getCharDataFull()

elif args.dataset_id == 'WAF':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getWafer()
    
elif args.dataset_id == 'SIN':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getSins() 

elif args.dataset_id == 'MSO':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getSins()  
    
elif args.dataset_id == 'ODE':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getODE()  
    
elif args.dataset_id == 'ECG2':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getECGDataFull()  

elif args.dataset_id == 'BLOOD':        
    (train_data, train_labels, train_len, train_targets, K_tr,
        valid_data, valid_labels, valid_len, valid_targets, K_vs,
        test_data, test_labels, test_len, test_targets, K_ts) = getBlood()  
    
else:
    sys.exit('Invalid dataset_id')

print('\n**** Processing {}: Tr{}, Ts{} ****\n'.format(args.dataset_id, train_data.shape, test_data.shape))

# sort test data (for visualize the learned K)
#sort_idx = np.argsort(test_labels,axis=0)[:,0]
#test_labels = test_labels[sort_idx,:]
#test_data = test_data[:,sort_idx,:]
#test_targets = test_targets[:,sort_idx,:]
#test_len = test_len[sort_idx]

# target kernel matrix
if args.plot_on:
    plt.matshow(K_ts,cmap='binary_r')
    plt.title('prior K')
    plt.gca().axes.get_xaxis().set_ticks([])
    plt.gca().axes.get_yaxis().set_ticks([])
    plt.show()

# ================== RESTORE AND EVAL MODEL ==================
tf.reset_default_graph()
sess = tf.Session()
    
# restore graph
new_saver = tf.train.import_meta_graph("../models/tkae_"+args.graph_name+".ckpt.meta", clear_devices=True)
new_saver.restore(sess, "../models/tkae_"+args.graph_name+".ckpt")  

encoder_inputs = tf.get_collection("encoder_inputs")[0]
encoder_inputs_length = tf.get_collection("encoder_inputs_length")[0]
decoder_outputs = tf.get_collection("decoder_outputs")[0]
inf_outputs = tf.get_collection("inf_outputs")[0]
inf_loss = tf.get_collection("inf_loss")[0]
context_vector = tf.get_collection("context_vector")[0]
code_K = tf.get_collection("code_K")[0]

# get context vectors from training data
fdtr = {encoder_inputs: train_data,
        encoder_inputs_length: train_len}
tr_context = sess.run(context_vector, fdtr)

# get context vectors and predictions from test data
fdts = {encoder_inputs: test_data,
        encoder_inputs_length: test_len}
ts_pred, ts_context, ts_code_K = sess.run([inf_outputs, context_vector, code_K], fdts)
sess.close()

# =============== DATA ANALYSIS ===============
if args.plot_on:
    
    # plot kernel code
    plt.matshow(ts_code_K,cmap='binary_r')
    plt.title('code K')
    plt.gca().axes.get_xaxis().set_ticks([])
    plt.gca().axes.get_yaxis().set_ticks([])
    plt.show()
    
    plt_idx1 = np.random.randint(low=0, high=test_data.shape[1])
    target = test_data[:,plt_idx1,:]
    pred = ts_pred[:-1,plt_idx1,:]
    target = np.reshape(target.T, (target.shape[0]*target.shape[1]))
    pred = np.reshape(pred.T, (pred.shape[0]*pred.shape[1]))  
    plt.plot(target, label='target')
    plt.plot(pred, label='pred')
    plt.legend(loc='upper right')
    plt.show(block=True)
    np.savetxt('../logs/TKAE_pred',pred)
    np.savetxt('../logs/true_signal',target)

# 2d plot of the codes
if args.plot_code:
    plt.scatter(ts_context[:,0],ts_context[:,1],s=60,c=test_labels,marker='.',linewidths = 0,cmap='Paired')
    plt.gca().axes.get_xaxis().set_ticks([])
    plt.gca().axes.get_yaxis().set_ticks([])
    plt.show()

# dim reduction plots
if args.dim_red:
    dim_reduction_plot(ts_context, test_labels)

# MSE and corr
test_mse, test_corr = mse_and_corr(test_targets, ts_pred, test_len)
print('Test MSE=%.3f, Corr=%.3f'%(test_mse, test_corr))

# kNN classification on the codes
acc, f1 = classify_with_knn(tr_context, train_labels[:, 0], ts_context, test_labels[:, 0], k=3)
print('kNN -- acc: %.3f, F1: %.3f'%(acc, f1))