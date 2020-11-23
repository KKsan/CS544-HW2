# -*- coding: utf-8 -*-
"""HW2_submission.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1RgipWzUfPQJMZOrNpzx6xnfQF5SOtgWP

#Introduction 

### In this assignment, we ask you to build neural language models with recurrent neural networks. We provide the starter code for you. You need to implement RNN models here and write a separate report describing your experiments. Simply copying from other sources will be considered as plagiarism.

# Tasks

*   [**Task 1.1: 10 Pts**] Additional data processing (5 Pts) with comments (5 Pts).

*   [**Task 1.2: 50 Pts**] Complete this end-to-end pipeline with RNN and LSTM architectures and save the best model object for autograding (40 Pts). Clearly comment and explain your code using **+ Text** functionality in Colab (10 Pts).
*   [**Task 2: 20 Pts**] Hyper-parameters tuning using the validation set. You need to write a separate report describing your experiments by tuning three hyper-parameters. See more details in Task 3.
*   [**Task 3: 20 Pts**] Submit the best model object and class to Vocareum for grading. 
*   [**Task 4: Extra Credits**] Try adding addtional linguistic features or other DL architectures to improve your model: char-RNN, attention mechanisum, etc. You have to implement these models in the framework we provide and clearly comment your code. 


**Simply copying from other sources will be considered as plagiarism.**

# Download Data and Tokenizer
"""

! git clone https://github.com/rujunhan/CSCI-544.git
# Install Tokenizer
! pip install mosestokenizer

"""# Data Processing

I added a function called process_str(). 
*   @param str: a string
*   @output: a processed string

The one line function does the following: it uses string.lower() to convert all letters to lower case, then it uses regex to replace all numbers in the string with '\<num\>'. However numbers with preceding letters are excluded from the match. Then it addes '\<bos\>' to the head of the string, and '\<eos\>' to the end of the string. Finally it returns the modified string.

Then I call the process_str() function on the joined token string (line 27 and 32), and write the processed string to the file.
"""

from pathlib import Path
from tqdm import tqdm 
from mosestokenizer import MosesTokenizer
import logging as log
import re

log.basicConfig(level=log.INFO)
tokr = MosesTokenizer()

def read_tokenized(dir):
  """Tokenization wrapper"""
  inputfile = open(dir)
  for sent in inputfile:
    yield tokr(sent.strip())

def process_str(str):
  #function does the following:
  #1. convert string to lower case
  #2. replace numbers with <num> but ignore matches that have preceding letters
  #3. add <bos> to the start of string
  #4. add <eos> to the end of string
  return '<bos> ' + re.sub('(?<![A-Za-z])(\d+)', '<num>', str.lower()) + ' <eos>\n'

  
train_file = Path('train.txt')
with train_file.open('w') as w:
  for toks in tqdm(read_tokenized(Path('CSCI-544/hw2/train.txt'))):
    w.write(process_str(" ".join(toks)))
    
dev_file = Path('dev.txt')
with dev_file.open('w') as w:
  for toks in tqdm(read_tokenized(Path('CSCI-544/hw2/dev.txt'))):
    w.write(process_str(" ".join(toks)))

! ls -lh

! head train.txt

"""# Task 1.1: additional data processing [5 pts + 5 pts comments]

Modify the above data processing code by

1.   making all tokens lower case
2.   mapping all numbers to a special symbol $\langle num\rangle$
3.   adding $\langle bos\rangle$ and $\langle eos\rangle$ to the beginning and the end of a sentence

### NOTE 
MAX_TYPES, MIN_FREQ and BATCH_SIZE are fixed hyper-parameters for data. You are **NOT ALLOWED** to change these for fair comparison. The auto-grading script on Vocareum also uses these fixed values, so make sure you don't change them. We will ask you to experiment with other hyper-parameters related to model and report results.
"""

from typing import List, Iterator, Set, Dict, Optional, Tuple
from collections import Counter
from pathlib import Path
import torch

RESERVED = ['<pad>', '<unk>']

PAD_IDX = 0 
UNK_IDX = 1
MAX_TYPES = 10_000
BATCH_SIZE = 256
MIN_FREQ = 5
RUN_FNN = False
RUN_RNN = False
RUN_LSTM = False

class Vocab:
  """ Mapper of words <--> index """

  def __init__(self, types):
    # types is list of strings
    assert isinstance(types, list)
    assert isinstance(types[0], str)

    self.idx2word = types
    self.word2idx = {word: idx for idx, word in enumerate(types)}
    assert len(self.idx2word) == len(self.word2idx)  # One-to-One

  def __len__(self):
    return len(self.idx2word)
  
  def save(self, path: Path):
    log.info(f'Saving vocab to {path}')
    with path.open('w') as wr:
      for word in self.idx2word:
        wr.write(f'{word}\n')
 
  @staticmethod
  def load(path):
    log.info(f'loading vocab from {path}')
    types = [line.strip() for line in path.open()]
    for idx, tok in enumerate(RESERVED): # check reserved
      assert types[idx] == tok
    return Vocab(types)

  @staticmethod
  def from_text(corpus: Iterator[str], max_types: int,
                             min_freq: int = 5):
    """
    corpus: text corpus; iterator of strings
    max_types: max size of vocabulary
    min_freq: ignore word types that have fewer ferquency than this number
    """
    log.info("building vocabulary; this might take some time")
    term_freqs = Counter(tok for line in corpus for tok in line.split())
    for r in RESERVED:
      if r in term_freqs:
        log.warning(f'Found reserved word {r} in corpus')
        del term_freqs[r]
    term_freqs = list(term_freqs.items())
    log.info(f"Found {len(term_freqs)} types; given max_types={max_types}")
    term_freqs = {(t, f) for t, f in term_freqs if f >= min_freq}
    log.info(f"Found {len(term_freqs)} after dropping freq < {min_freq} terms")
    term_freqs = sorted(term_freqs, key=lambda x: x[1], reverse=True)
    term_freqs = term_freqs[:max_types]
    types = [t for t, f in term_freqs]
    types = RESERVED + types   # prepend reserved words
    return Vocab(types)


train_file = Path('train.txt')
vocab_file = Path('vocab.txt')

if not vocab_file.exists():
  train_corpus = (line.strip() for line in train_file.open())
  vocab = Vocab.from_text(train_corpus, max_types=MAX_TYPES, min_freq=MIN_FREQ)
  vocab.save(vocab_file)
else:
  vocab = Vocab.load(vocab_file)

log.info(f'Vocab has {len(vocab)} types')

import copy

class TextDataset:

  def __init__(self, vocab: Vocab, path: Path):
    self.vocab = vocab
    log.info(f'loading data from {path}')
    # for simplicity, loading everything to memory; on large datasets this will cause OOM

    text = [line.strip().split() for line in path.open()]

    # words to index; out-of-vocab words are replaced with UNK
    xs = [[self.vocab.word2idx.get(tok, UNK_IDX) for tok in tokss] 
                 for tokss in text]
    
    self.data = xs
    
    log.info(f"Found {len(self.data)} records in {path}")

  def as_batches(self, batch_size, shuffle=False): # data already shuffled
    data = self.data
    if shuffle:
      random.shuffle(data)
    for i in range(0, len(data), batch_size): # i incrememt by batch_size
      batch = data[i: i + batch_size]  # slice
      yield self.batch_as_tensors(batch)
  
  @staticmethod
  def batch_as_tensors(batch):
    
    n_ex = len(batch)
    max_len = max(len(seq) for seq in batch)
    seqs_tensor = torch.full(size=(n_ex, max_len), fill_value=PAD_IDX,
                             dtype=torch.long)
    
    for i, seq in enumerate(batch):
      seqs_tensor[i, 0:len(seq)] = torch.tensor(seq)
      
    return seqs_tensor

train_data = TextDataset(vocab=vocab, path=train_file)
dev_data = TextDataset(vocab=vocab, path=Path('dev.txt'))

import torch.nn as nn
class FNN_LM(nn.Module):

  def __init__(self, vocab_size, n_class, emb_dim=50, hid=100, dropout=0.2):
    super(FNN_LM, self).__init__()
    self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                  embedding_dim=emb_dim, 
                                  padding_idx=PAD_IDX)
    self.linear1 = nn.Linear(emb_dim, hid)
    self.linear2 = nn.Linear(hid, n_class)
    self.dropout = nn.Dropout(p=dropout)

  def forward(self, seqs, log_probs=True):
    """Return log Probabilities"""
    batch_size, max_len = seqs.shape
    embs = self.embedding(seqs)  # embs[Batch x SeqLen x EmbDim]
    embs = self.dropout(embs)
    embs = embs.sum(dim=1)   # sum over all all steps in seq    
    
    hid_activated = torch.relu(self.linear1(embs)) # Non linear
    scores = self.linear2(hid_activated)

    if log_probs:
      return torch.log_softmax(scores, dim=1)
    else:
      return torch.softmax(scores, dim=1)

def save_model_object(model):
  torch.save({'state_dict': model.state_dict()}, "best_model.pt")
  return

"""Result from one trial of FNN: <br/>
INFO:root:Epoch 0 complete; Losses: Train=2.51379 Valid=2.20049<br/>
INFO:root:Epoch 1 complete; Losses: Train=2.15637 Valid=2.13673<br/>
INFO:root:Epoch 2 complete; Losses: Train=2.10395 Valid=2.10767<br/>
INFO:root:Epoch 3 complete; Losses: Train=2.07418 Valid=2.08653<br/>
INFO:root:Epoch 4 complete; Losses: Train=2.05346 Valid=2.07148<br/>
"""

# Trainer Optimizer 
import time
from tqdm import tqdm
import torch.optim as optim
import gc

def save_model(model, model_name, para_name, para_value):
  model_save_name = model_name + '_' + para_name + '_' + str(para_value) + '.pt'
  print('\n{} saved!'.format(model_save_name))
  path = F"/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/Model_Savepoints/{model_save_name}" 
  torch.save(model.state_dict(), path)
  
def read_model(model, model_save_name):
  print('\n{} loaded!'.format(model_save_name))
  path = F"/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/Model_Savepoints/{model_save_name}"
  model.load_state_dict(torch.load(path))

def train(model, n_epochs, batch_size, train_data, valid_data, device=torch.device('cuda')):
  log.info(f"Moving model to {device}")
  model = model.to(device)   # move model to desired device 
  optimizer = optim.Adam(params=model.parameters())
  log.info(f"Device for training {device}")
  losses = []
  for epoch in range(n_epochs):
    start = time.time()
    num_toks = 0
    train_loss = 0.
    n_train_batches = 0

    model.train() # switch to train mode 
    with tqdm(train_data.as_batches(batch_size=BATCH_SIZE), leave=False) as data_bar:
      for seqs in data_bar:
        seq_loss = torch.zeros(1).to(device)
        for i in range(1, seqs.size()[1]-1):
          # Move input to desired device
          cur_seqs = seqs[:, :i].to(device) # take w0...w_(i-1) python indexing
          cur_tars = seqs[:, i].to(device)  # predict w_i

          log_probs = model(cur_seqs)
          seq_loss += loss_func(log_probs, cur_tars).sum() / len(seqs)
        
        seq_loss /= (seqs.shape[1] - 1) # only n-1 toks are predicted
        train_loss += seq_loss.item()
        n_train_batches += 1

        optimizer.zero_grad()         # clear grads
        seq_loss.backward()
        optimizer.step()
        
        torch.cuda.empty_cache()      #clear cache
        gc.collect()                  #garbage collection to release memory

        pbar_msg = f'Loss:{seq_loss.item():.4f}'
        data_bar.set_postfix_str(pbar_msg)

    # Run validation
    with torch.no_grad():
      model.eval() # switch to inference mode -- no grads, dropouts inactive
      val_loss = 0
      n_val_batches = 0
      for seqs in valid_data.as_batches(batch_size=batch_size, shuffle=False):
        # Move input to desired device
        seq_loss = torch.zeros(1).to(device)
        for i in range(1, seqs.size()[1]-1):
          # Move input to desired device
          cur_seqs = seqs[:, :i].to(device)
          cur_tars = seqs[:, i].to(device)

          log_probs = model(cur_seqs)
          seq_loss += loss_func(log_probs, cur_tars).sum() / len(seqs)
        seq_loss /= (seqs.shape[1] - 1)
        val_loss += seq_loss.item() 
        n_val_batches += 1
        
    save_model_object(model)
    avg_train_loss = train_loss / n_train_batches
    avg_val_loss = val_loss / n_val_batches
    losses.append((epoch, avg_train_loss, avg_val_loss))
    log.info(f"Epoch {epoch} complete; Losses: Train={avg_train_loss:G} Valid={avg_val_loss:G}")
    save_model(model, 'RNN_best_model_1_150_100_0.02' + str(epoch), 'loss', avg_val_loss)
  return losses

if RUN_FNN:
  model = FNN_LM(vocab_size=len(vocab), n_class=len(vocab))
  loss_func = nn.NLLLoss(reduction='none')
  losses = train(model, n_epochs=5, batch_size=BATCH_SIZE, train_data=train_data,
                  valid_data=dev_data)

! ls -l

"""# Task 1.2: RNNs [50 pts]

1.   Under the given FNN_LM framework, modify the code to implement RNN model [15 pts + 5 pts comments]
2.   Repeat this step for LSTM model [15 pts + 5 pts comments]
3.   Write a report comparing your results for these three models [10 pts]

I followed the FNN_LM framework and implemented the RNN_LM class. <br/>

Constructor __init__()<br/>
*   @param vocab_size: amount of vocabularies
*   @param n_class: same as vocab_size
*   @param emb_dim: embedding dimension, number of expected features in training set, default to 50
*   @param hid: number of features in hidden state h, default to 100
*   @param num_layers: number of recurrent layers, default to 1
*   @param dropout: dropout probability for dropout layer, default to 0.1
*   @output: none, modules should be initiated

In the class constructor, similar to FNN_LM, I firstly set up the embedding module with given vocabulary size, embedding dimension, and padding (default to 0). Then I set up the built-in RNN module with embedding dimensions, number of hidden layers, and number of RNN layers. I used Rectified linear units (Relu) for the RNN activation function because it's faster to compute. I also turn the batch_first to true so the input and output tensors are provided as (batch, seq, feature). I also initiate the dropout module with the specified dropout ratio for input embeddings (probability that a value will be zeroed). Then I initiate a linear layer that will be used for applying a linear transformation to the output from RNN. I also stored hid and num_layers as class attributes to be used later. <br/>

forward step forward()<br/>
*   @param seqs: sequences of input text
*   @param log_probs: boolean to decide using log softmax or regular softmax for forward step
*   @output: value calcualted by softmax or softmax followed by logarithm.

In the forward() function, I first put input text sequence into embeddings. Then I apply the dropout to input embeddings to prevent overfitting and improve model performance. Then I run the embedding through the RNN we initiated earlier. The output of RNN is (output, hn) in which hn is the hidden state for t = seq_len (the very last hidden state) with shape (num_layers * num_directions, batch, hid). hn is equivalent to output[-1]. We sequeeze the hn to remove dimensions of size 1. Then we apply the linear transformation on hn and apply a softmax followed by a logarithm to the outcome of the linear transformation.

I set up a global boolean constant to control which model to run. In the particular case of RNN, I used the same negative log loss function as the FNN and calculated the losses. Initiatized an RNN model using the RNN_LM class, and trained my model using the train() function.

Result from one trial of RNN: <br/>
INFO:root:Epoch 0 complete; Losses: Train=2.23546 Valid=1.9182 <br/>
INFO:root:Epoch 1 complete; Losses: Train=1.83006 Valid=1.81631  <br/>
INFO:root:Epoch 2 complete; Losses: Train=1.75349 Valid=1.76443  <br/>
INFO:root:Epoch 3 complete; Losses: Train=1.70767 Valid=1.73208  <br/>
INFO:root:Epoch 4 complete; Losses: Train=1.67561 Valid=1.70967  <br/>
"""

class RNN_LM(nn.Module):
    def __init__(self, vocab_size, n_class, emb_dim=50, hid=100, num_layers=1, dropout=0.1):
        super(RNN_LM, self).__init__()
               
        self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                      embedding_dim=emb_dim, 
                                      padding_idx=PAD_IDX)
        
        self.rnn = nn.RNN(input_size=emb_dim, 
                          hidden_size=hid, 
                          num_layers=num_layers,
                          nonlinearity='relu',
                          batch_first=True)  #(batch, seq, feature)
        
        self.linear = nn.Linear(hid, n_class)
        self.dropout = nn.Dropout(p=dropout)
        
        self.hid = hid;
        self.num_layers = num_layers;
        
        
    def forward(self, seqs, log_probs=True):
        batch_size, max_len = seqs.shape
        
        embs = self.embedding(seqs) #(batch, seq, feature)
        embs = self.dropout(embs)   #zero some input
        output, hn = self.rnn(embs) #run thru rnn
        hn = hn.squeeze()           #remove dimension of 1
        scores = self.linear(hn)    #linear transformation
        
        if log_probs:
          return torch.log_softmax(scores, dim=1)
        else:
          return torch.softmax(scores, dim=1)

if RUN_RNN:
  model = RNN_LM(vocab_size=len(vocab), n_class=len(vocab))
  loss_func = nn.NLLLoss(reduction='none')
  losses = train(model, n_epochs=5, batch_size=BATCH_SIZE, train_data=train_data,
                  valid_data=dev_data)

"""LSTM_LM is very similar to RNN_LM except that it uses the LSTM module. <br/>

Constructor __init__()<br/>
*   @param vocab_size: amount of vocabularies
*   @param n_class: same as vocab_size
*   @param emb_dim: embedding dimension, number of expected features in training set, default to 50
*   @param hid: number of features in hidden state h, default to 50 to avoid runtime memory error
*   @param num_layers: number of recurrent layers, default to 1
*   @param dropout: dropout probability for dropout layer, default to 0.1
*   @output: none, modules should be initiated

In the class constructor, similar to RNN_LM, I firstly set up the embedding module with given vocabulary size, embedding dimension, and padding (default to 0). Note that I cut down the hid from 100 to 50 in order to avoid CUDA OUT OF MEMORY runtime error. Then I set up the built-in LSTM module with embedding dimensions, number of hidden layers, number of LSTM layers, and drop out rate. I also turn the batch_first to true so the input and output tensors are provided as (batch, seq, feature). Then I initiate a linear layer that will be used for applying a linear transformation to the output from LSTM. A dropout module is also initiated. I also stored hid and num_layers as class attributes to be used later. <br/>

forward step forward() input <br/>
*   @param seqs: sequences of input text
*   @param log_probs: boolean to decide using log softmax or regular softmax for forward step
*   @output: value calcualted by softmax or softmax followed by logarithm.

In the forward() function, I first put input text sequence into embeddings. Then I apply dropout to the input embedding in order to prevent overfitting and improve model performance. Then I run the embedding through the LSTM we initiated earlier. The output of LSTM is (output, (hn, cn)) in which hn is the hidden state for t = seq_len (the very last hidden state) with shape (num_layers * num_directions, batch, hid) and cn is the cell state for t = seq_len. hn is equivalent to output[-1]. We sequeeze the hn to remove dimensions of size 1. Then we apply the linear transformation on hn and apply a softmax followed by a logarithm to the outcome of the linear transformation.

I set up a global boolean constant to control which model to run. In the particular case of LSTM, I used the same negative log loss function as the RNN and calculated the losses.

Result from one trial of LSTM with hid=50 <br/>
INFO:root:Epoch 0 complete; Losses: Train=2.7722 Valid=2.05054 <br/>
INFO:root:Epoch 1 complete; Losses: Train=1.94388 Valid=1.90909 <br/>
INFO:root:Epoch 2 complete; Losses: Train=1.8456 Valid=1.83904 <br/>
INFO:root:Epoch 3 complete; Losses: Train=1.78997 Valid=1.79681 <br/>
INFO:root:Epoch 4 complete; Losses: Train=1.7532 Valid=1.76735 <br/>
"""

class LSTM_LM(nn.Module):
    def __init__(self, vocab_size, n_class, emb_dim=50, hid=50, num_layers=1, dropout=0.1):
        super(LSTM_LM, self).__init__()
        self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                  embedding_dim=emb_dim, padding_idx=PAD_IDX)
        
        self.lstm = nn.LSTM(input_size=emb_dim, 
                            hidden_size=hid, 
                            num_layers=num_layers,
                            batch_first=True)  #(batch, seq, feature)
        
        self.linear = nn.Linear(hid, n_class)
        self.dropout = nn.Dropout(p=dropout)
        
        self.hid = hid;
        self.num_layers = num_layers;
        
    def forward(self, seqs, log_probs=True):
        batch_size, max_len = seqs.shape
        
        embs = self.embedding(seqs)     #(batch, seq, feature)
        embs = self.dropout(embs)
        output, hn_cn = self.lstm(embs) #hn_cn=(hn, cn)

        hn = hn_cn[0].squeeze()         #remove dimension of 1
        scores = self.linear(hn)        #linear transformation
        
        if log_probs:
          return torch.log_softmax(scores, dim=1)
        else:
          return torch.softmax(scores, dim=1)
        
if RUN_LSTM:
  model = LSTM_LM(vocab_size=len(vocab), n_class=len(vocab))
  loss_func = nn.NLLLoss(reduction='none')
  losses = train(model, n_epochs=5, batch_size=BATCH_SIZE, train_data=train_data,
                  valid_data=dev_data)

"""# Task 2: Hyper-parameters Tuning [20 pts]
You may observe that there are multiple hyper-parameters used in the pipeline. Choose 3 out of 5 following hyper-parameters and try at least 5 different values for each of them and report their corresponding performances on the train / dev datasets. Explain why you think larger or smaller values may cause the differenes you observed.

1.   emb_dim: embedding size
2.   hid: hidden layer dimension
3.   num_layers: number of RNN layers
4.   dropout ratio
5.   n_epochs


"""

! pwd
! ls -l

TUNE_RNN_DR = False
TUNE_RNN_ED = False
TUNE_RNN_HID = False
TUNE_LSTM_DR = False
TUNE_LSTM_ED = False
TUNE_LSTM_HID = False

EPOCH_NUM = 5
best_dr = 0;
best_ed = 0;
best_hid = 0;
best_valid_loss = 100;

#value to test
dropout = 0.02
emb_dim = 186
hid = 100
  
if TUNE_RNN_DR:
  print('Tunning RNN dropout ratio...\n')
  f1 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/rnn_dr_tuning.txt','a+')
  f1.write('RNN tuning result:\nepoch     train_loss     valid_loss\n')
        
  print('\ndropout {}\n'.format(dropout))
  f1.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(dropout, 50, 100))

  model = RNN_LM(vocab_size=len(vocab), 
                 n_class=len(vocab),
                 emb_dim=emb_dim,
                 dropout=dropout,
                 hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f1.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_dr = dropout;

  save_model(model, 'RNN', 'dropout', dropout)
            
  f1.write('best_dr: {} best_valid_loss: {}\n'.format(best_dr, best_valid_loss))
  f1.close()
  
  #==================================================
if TUNE_RNN_ED:
  print('Tunning RNN emb_dim...\n')
  f2 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/rnn_ed_tuning.txt','a+')
  f2.write('RNN tuning result:\nepoch     train_loss     valid_loss\n')
  best_valid_loss = 100;
       
  print('\ned {}\n'.format(emb_dim))
  f2.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(0.1, emb_dim, 100))

  model = RNN_LM(vocab_size=len(vocab), 
                 n_class=len(vocab),
                 emb_dim=emb_dim,
                 dropout=dropout,
                 hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f2.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_ed = emb_dim;

  save_model(model, 'RNN', 'ed', emb_dim)

  f2.write('best_ed: {} best_valid_loss: {}\n'.format(best_ed, best_valid_loss))
  f2.close() 
  
  #==================================================
if TUNE_RNN_HID:
  print('Tunning RNN hid...\n')
  f3 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/rnn_hid_tuning.txt','a+')
  f3.write('RNN tuning result:\nepoch     train_loss     valid_loss\n')
  best_valid_loss = 100;
    
  print('\nhid {}\n'.format(hid))
  f3.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(0.1, 50, hid))

  model = RNN_LM(vocab_size=len(vocab), 
                 n_class=len(vocab),
                 emb_dim=emb_dim,
                 dropout=dropout,
                 hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f3.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_hid = hid;

  save_model(model, 'RNN', 'hid', hid)
    
  f3.write('best_hid: {} best_valid_loss: {}\n'.format(best_hid, best_valid_loss))
  f3.close()
  
  #=======================================================================
  #=======================================================================
  #=======================================================================
  
if TUNE_LSTM_DR:
  print('Tunning LSTM dropout ratio...\n')
  f4 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/lstm_dr_tuning.txt','a+')
  f4.write('LSTM tuning result:\nepoch     train_loss     valid_loss\n')
        
  print('\ndropout {}\n'.format(dropout))
  f4.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(dropout, 50, 50))

  model = LSTM_LM(vocab_size=len(vocab), 
                  n_class=len(vocab),
                  emb_dim=emb_dim,
                  dropout=dropout,
                  hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f4.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_dr = dropout;
    
  save_model(model, 'LSTM', 'dropout', dropout)
            
  f4.write('best_dr: {} best_valid_loss: {}\n'.format(best_dr, best_valid_loss))
  f4.close()
  
  #==================================================
if TUNE_LSTM_ED:
  print('Tunning LSTM emb_dim...\n')
  f5 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/lstm_ed_tuning.txt','a+')
  f5.write('LSTM tuning result:\nepoch     train_loss     valid_loss\n')
  best_valid_loss = 100;    
        
  print('\ned {}\n'.format(emb_dim))
  f5.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(0.1, emb_dim, 50))

  model = LSTM_LM(vocab_size=len(vocab), 
                  n_class=len(vocab),
                  emb_dim=emb_dim,
                  dropout=dropout,
                  hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f5.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_ed = emb_dim;

  save_model(model, 'LSTM', 'ed', emb_dim)

  f5.write('best_ed: {} best_valid_loss: {}\n'.format(best_ed, best_valid_loss))
  f5.close() 
  
  #==================================================
if TUNE_LSTM_HID: 
  print('Tunning LSTM hid...\n')
  f6 = open('/content/drive/My Drive/Colab Notebooks/CSCI544_HW2/lstm_hid_tuning.txt','a+')
  f6.write('LSTM tuning result:\nepoch     train_loss     valid_loss\n')
  best_valid_loss = 100;
        
  print('\nhid {}\n'.format(hid))
  f6.write('-----------------------\ndr {}     ed {}     hid {}\n'.format(0.1, 50, hid))

  model = LSTM_LM(vocab_size=len(vocab), 
                  n_class=len(vocab),
                  emb_dim=emb_dim,
                  dropout=dropout,
                  hid=hid)

  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=EPOCH_NUM, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  for result in losses:
    f6.write('{}     {}     {}\n'.format(result[0], result[1], result[2]))

    if(result[2] < best_valid_loss):
      best_valid_loss = result[2]
      best_hid = hid;

  save_model(model, 'LSTM', 'hid', hid)
            
  f6.write('best_hid: {} best_valid_loss: {}\n'.format(best_hid, best_valid_loss))
  f6.close()
     
print("DONE TUNING!")

from google.colab import drive
drive.mount('/content/drive')

"""#Task 3: Submitting your model class and object
1. After you find the best model architecture, rename your best model as **BEST_MODEL** and re-run train() to save your model.
2. Download model object and locate it (best_model.pt file) in your local direcotry and submit it to Vocareum.
3. Copy your **BEST_MODEL** class into a python script: best_model.py and submit it to Vocareum.
4. Download you **vocab.txt** file and submit it with your model files.

In summary, you will need a **best_model.py** file,  a **best_model.pt** object and a **vocab.txt** file to successfully run the auto-grading on Vocareum.

We made the evaluation code visible (but not editable) to everyone on Vocareum. You can find it here: resource/asnlib/public/evaluation.py

See below for an example. Rename FNN() class as BEST_MODEL. Modify and save the entire script below as best_model.py
"""

import torch
import torch.nn as nn

from google.colab import files

class BEST_MODEL(torch.nn.Module):
  def __init__(self, vocab_size, n_class, emb_dim=150, hid=100, num_layers=1, dropout=0.02):
        super(BEST_MODEL, self).__init__()
               
        self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                      embedding_dim=emb_dim, 
                                      padding_idx=0)
        
        self.rnn = nn.RNN(input_size=emb_dim, 
                          hidden_size=hid, 
                          num_layers=num_layers,
                          nonlinearity='relu',
                          batch_first=True)  #(batch, seq, feature)
        
        self.linear = nn.Linear(hid, n_class)
        self.dropout = nn.Dropout(p=dropout)
        
        self.hid = hid;
        self.num_layers = num_layers;
        
        
  def forward(self, seqs, log_probs=True):
      batch_size, max_len = seqs.shape

      embs = self.embedding(seqs) #(batch, seq, feature)
      embs = self.dropout(embs)   #zero some input
      output, hn = self.rnn(embs) #run thru rnn
      hn = hn.squeeze()           #remove dimension of 1
      scores = self.linear(hn)    #linear transformation

      if log_probs:
        return torch.log_softmax(scores, dim=1)
      else:
        return torch.softmax(scores, dim=1)
    

RUN_BEST_MODEL = True
    
if RUN_BEST_MODEL:
  print('\nRunning best model...\n')

  model = BEST_MODEL(vocab_size=len(vocab), 
                     n_class=len(vocab),
                     emb_dim=150,
                     hid=100,
                     dropout=0.02)
  
  read_model(model, 'RNN_best_model_1_150_100_0.02_epoch_4.pt')
  
  loss_func = nn.NLLLoss(reduction='none')

  losses = train(model, 
                 n_epochs=5, 
                 batch_size=BATCH_SIZE, 
                 train_data=train_data,
                 valid_data=dev_data)

  print('\nDone running best model, saved to google drive!\n')



"""# Task 4:  [Extra Credits 5Pts]

Enhance the current model with additional linguistic features or DL models
"""

