import tensorflow as tf
import argparse, sys
from TS_datasets import getSynthData, getECGData, getJapData
import time
import numpy as np
import matplotlib.pyplot as plt

plot_on = 0

# parse input data
parser = argparse.ArgumentParser()
parser.add_argument("--dataset_id", default='JAP', help="ID of the dataset (SYNTH, ECG, JAP)", type=str)
parser.add_argument("--code_size", default=5, help="size of the code", type=int)
parser.add_argument("--num_epochs", default=5000, help="number of epochs in training", type=int)
parser.add_argument("--batch_size", default=50, help="number of samples in each batch", type=int)
parser.add_argument("--max_gradient_norm", default=1.0, help="max gradient norm for gradient clipping", type=float)
parser.add_argument("--w_reg", default=0.001, help="weight of the regularization in the loss function", type=float)
parser.add_argument("--learning_rate", default=0.001, help="Adam initial learning rate", type=float)
args = parser.parse_args()


# ================= DATASET =================
if args.dataset_id == 'SYNTH':
    (train_data, train_labels, _, _, _,
        valid_data, _, _, _, _,
        test_data, _, _, _, _) = getSynthData(name='Lorentz', tr_data_samples=2000, 
                                                 vs_data_samples=2000, 
                                                 ts_data_samples=2000)
    train_data = train_data[:,:,0].T
    valid_data = valid_data[:,:,0].T
    test_data = test_data[:,:,0].T
    
elif args.dataset_id == 'ECG':
    (train_data, train_labels, _, _, _,
        valid_data, _, _, _, _,
        test_data, _, _, _, _) = getECGData(tr_ratio = 0.4)
    
    train_data = train_data[:,:,0].T
    valid_data = valid_data[:,:,0].T
    test_data = test_data[:,:,0].T
       
elif args.dataset_id == 'JAP':        
    (train_data, train_labels, _, _, _,
        valid_data, _, _, _, _,
        test_data, _, _, _, _) = getJapData()
    
    # transpose and reshape
    train_data = np.transpose(train_data,axes=[1,0,2])
    train_data = np.reshape(train_data, (train_data.shape[0], train_data.shape[1]*train_data.shape[2]))
    valid_data = np.transpose(valid_data,axes=[1,0,2])
    valid_data = np.reshape(valid_data, (valid_data.shape[0], valid_data.shape[1]*valid_data.shape[2]))
    test_data = np.transpose(test_data,axes=[1,0,2])
    test_data = np.reshape(test_data, (test_data.shape[0], test_data.shape[1]*test_data.shape[2]))
else:
    sys.exit('Invalid dataset_id')


input_length = train_data.shape[1]
print('\n**** Processing {}: Tr{}, Vs{}, Ts{} ****\n'.format(args.dataset_id, train_data.shape, valid_data.shape, test_data.shape))


# ================= GRAPH =================

# init session
tf.reset_default_graph() # needed when working with iPython
sess = tf.Session()

# placeholders
encoder_inputs = tf.placeholder(shape=(None,input_length), dtype=tf.float32, name='encoder_inputs')

# encoder
with tf.variable_scope("Encoder"):
#    enc_out = tf.contrib.layers.fully_connected(encoder_inputs,
#                                           num_outputs=input_length,
#                                           activation_fn=None,
#                                           )
#    
#    code = tf.contrib.layers.fully_connected(enc_out,
#                                           num_outputs=args.code_size,
#                                           activation_fn=tf.nn.tanh,
#                                           )
    
    code = tf.contrib.layers.fully_connected(encoder_inputs,
                                           num_outputs=args.code_size,
                                           activation_fn=tf.nn.tanh,
                                           )    
    
# decoder
with tf.variable_scope("Decoder"):
    dec_inp = tf.contrib.layers.fully_connected(code,
                                           num_outputs=input_length,
                                           activation_fn=tf.nn.tanh,
                                           )
    
    dec_out = tf.contrib.layers.fully_connected(dec_inp,
                                           num_outputs=input_length,
                                           activation_fn=None,
                                           )

# ----- LOSS --------

# reconstruction loss    
parameters = tf.trainable_variables()
optimizer = tf.train.AdamOptimizer(args.learning_rate)
reconstruct_loss = tf.losses.mean_squared_error(labels=dec_out, predictions=encoder_inputs)

# L2 loss
reg_loss = 0
for tf_var in tf.trainable_variables():
    reg_loss += tf.reduce_mean(tf.nn.l2_loss(tf_var))
        
tot_loss = reconstruct_loss + args.w_reg*reg_loss

# Calculate and clip gradients
gradients = tf.gradients(tot_loss, parameters)
clipped_gradients, _ = tf.clip_by_global_norm(gradients, args.max_gradient_norm)
update_step = optimizer.apply_gradients(zip(clipped_gradients, parameters))

sess.run(tf.global_variables_initializer())

# trainable parameters count
total_parameters = 0
for variable in tf.trainable_variables():
    shape = variable.get_shape()
    variable_parametes = 1
    for dim in shape:
        variable_parametes *= dim.value
    total_parameters += variable_parametes
print('Total parameters: {}'.format(total_parameters))

# ============= TENSORBOARD =============             
mean_grads = tf.reduce_mean([tf.reduce_mean(grad) for grad in gradients])
tf.summary.scalar('mean_grads', mean_grads)
tf.summary.scalar('reconstruct_loss', reconstruct_loss)
tvars = tf.trainable_variables()
for tvar in tvars:
    tf.summary.histogram(tvar.name.replace(':','_'), tvar)
merged_summary = tf.summary.merge_all()

# ================= TRAINING =================

# initialize training stuff
batch_size = args.batch_size
time_tr_start = time.time()
max_batches = train_data.shape[0]//batch_size
loss_track = []
min_vs_loss = np.infty
model_name = "/tmp/tkae_models/m_"+str(time.strftime("%Y%m%d-%H%M%S"))+".ckpt"
train_writer = tf.summary.FileWriter('/tmp/tensorboard', graph=sess.graph)
saver = tf.train.Saver()

try:
    for ep in range(args.num_epochs):
        
        # shuffle training data
        idx = np.random.permutation(train_data.shape[0])
        train_data_s = train_data[idx,:] 
        
        for batch in range(max_batches):
            
            fdtr = {encoder_inputs: train_data_s[(batch)*batch_size:(batch+1)*batch_size,:]}           
            _,train_loss = sess.run([update_step, reconstruct_loss], fdtr)    
            loss_track.append(train_loss)
            
        # check training progress on the validations set    
        if ep % 100 == 0:            
            print('Ep: {}'.format(ep))
            
            fdvs = {encoder_inputs: valid_data}
            outvs, lossvs, summary = sess.run([dec_out, reconstruct_loss, merged_summary], fdvs)
            train_writer.add_summary(summary, ep)
            print('VS loss=%.3f -- TR min_loss=.%3f'%(lossvs, np.min(loss_track)))     
            
            # Save model yielding best results on validation
            if lossvs < min_vs_loss:
                tf.add_to_collection("encoder_inputs",encoder_inputs)
                tf.add_to_collection("dec_out",dec_out)
                tf.add_to_collection("reconstruct_loss",reconstruct_loss)
                save_path = saver.save(sess, model_name)        
                                           
            # plot a random ts from the validation set
            if plot_on:
                plot_idx1 = np.random.randint(low=0,high=valid_data.shape[0])
                target = valid_data[plot_idx1,:]
                pred = outvs[plot_idx1,:-1]
                plt.plot(target, label='target')
                plt.plot(pred, label='pred')
                plt.legend(loc='upper right')
                plt.show(block=False)  
                                                    
except KeyboardInterrupt:
    print('training interrupted')

if plot_on:
    plt.plot(loss_track, label='loss_track')
    plt.legend(loc='upper right')
    plt.show(block=False)
    
time_tr_end = time.time()
print('Tot training time: {}'.format((time_tr_end-time_tr_start)//60) )

# ================= TEST =================
print('************ TEST ************ \n>>restoring from:'+model_name+'<<')

tf.reset_default_graph() # be sure that correct weights are loaded
saver.restore(sess, model_name)


ts_out, ts_loss = sess.run([dec_out, reconstruct_loss], {encoder_inputs: test_data})
print('Test MSE: %.3f' % (ts_loss))

plot_idx1 = np.random.randint(low=0,high=test_data.shape[0])
target = test_data[plot_idx1,:]
pred = ts_out[plot_idx1,:-1]
plt.plot(target, label='target')
plt.plot(pred, label='pred')
plt.legend(loc='upper right')
plt.show(block=False)  

train_writer.close()
sess.close()

with open('AE_results','a') as f:
    f.write('code_size: '+str(args.code_size)+', MSE: '+str(ts_loss)+'\n')

train_writer.close()
sess.close()