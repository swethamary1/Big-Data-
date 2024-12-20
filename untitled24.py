# Import necessary modules
from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession

# Create a Spark configuration
conf = SparkConf().setAppName("MySparkApp")  # Replace with your app name

# Create a Spark context
sc = SparkContext(conf=conf)

# Create a Spark session (optional, but often useful)
spark = SparkSession(sc)


# set all the s3 keys here
sc._jsc.hadoopConfiguration().set("fs.s3n.awsAccessKeyId", "insert your key")
sc._jsc.hadoopConfiguration().set("fs.s3n.awsSecretAccessKey", "insert your key")


# get the input data
input_file = sc.wholeTextFiles("insert your S3 bucket path")

# convert the input data to dataframe with two columns id and document
input_df = input_file.toDF()
input_df = input_df.toDF("id", "document")

display(input_df)

# get all the sentences from each of the input files.
import nltk
nltk.download('punkt')

from nltk.tokenize.punkt import PunktSentenceTokenizer

def getSentenceTokens(line):
    l = ' '.join(line.strip().split('\n'))

    sentence_tokenizer = PunktSentenceTokenizer()
    sentences = sentence_tokenizer.tokenize(l)
    return sentences


r = input_df.select("document")

sentences_df = r.rdd.map(lambda line: getSentenceTokens(line[0]))

sentences_df.take(1)

# get all the count vectorizer arrays using bag of words
from sklearn.feature_extraction.text import CountVectorizer
def countv(line):
  c = CountVectorizer()
  bow_array = c.fit_transform(line)
  b = bow_array.toarray()
  #lst.append(b)
  return b


count_vectors_df = sentences_df.map(lambda line: countv(line))

count_vectors_df.collect()

# get similarity graph using tf idf approach
from sklearn.feature_extraction.text import TfidfTransformer
def tf_idf(array):
  matrix_normalized = TfidfTransformer().fit_transform(array)
  similarity_graph = matrix_normalized * matrix_normalized.T
  return similarity_graph

similarity_graph_df = count_vectors_df.map(lambda array: tf_idf(array))

similarity_graph_df.take(1)

# get the scores using the pagerank algorithm on the graph constrcuted above
import networkx as nx

def getScores(array):
  nx_graph = nx.from_scipy_sparse_matrix(array)
  scores = nx.pagerank(nx_graph)
  return scores

scores_df = similarity_graph_df.map(lambda array: getScores(array))

scores_df.take(1)

import pandas as pd
panda = input_df.toPandas()

panda['sentence'] = sentences_df.collect()
panda['vectors'] = count_vectors_df.collect()
panda['tf_idf'] = similarity_graph_df.collect()
panda['scores'] = scores_df.collect()

import s3fs

s3 = s3fs.S3FileSystem(key="insert your key", secret="insert your key")
# Use 'w' for py3, 'wb' for py2


c = 0
lst = []
for i, j in panda.iterrows():
  ranked = sorted(((j['scores'][i],s) for i,s in enumerate(j['sentence'])),reverse=True)
  s=""
  for k in range(5):
    if k < len(ranked):
      s =s+ranked[k][1]
  lst.append(s)
  name = j['id']
  #with s3.open("insert your S3 bucket path"+name,'w') as f:
  #  f.write(s)
  #f.close()

panda['hypothesis'] = lst

panda['hypothesis'][0]

input_file1 = sc.wholeTextFiles("insert your S3 bucket path where original summaries is stored")
input_df1 = input_file1.toDF()
input_df1 = input_df1.toDF("id", "document")
summary = input_df1.toPandas()

input_df1.take(1)

import rouge


def prepare_results(p, r, f):

  return '\t{}:\t{}: {:5.2f}\t{}: {:5.2f}\t{}: {:5.2f}'.format(metric, 'P', 100.0 * p, 'R', 100.0 * r, 'F1', 100.0 * f)

s1 = ""
precision = []
recall = []
for aggregator in ['Avg']:
    print('Evaluation with {}'.format(aggregator))
    apply_avg = aggregator == 'Avg'
    apply_best = aggregator == 'Best'

    evaluator = rouge.Rouge(metrics=['rouge-n', 'rouge-l', 'rouge-w'],
                           max_n=2,
                           limit_length=True,
                           length_limit=100,
                           length_limit_type='words',
                           apply_avg=apply_avg,
                           alpha=0.5, # Default F1_score
                           weight_factor=1.2,
                           stemming=True)



    hypothesis=[]
    for i, j in panda.iterrows():
      h = j['hypothesis']
      hypothesis.append(h)


    reference=[]
    for i, j in summary.iterrows():
      r1 = j['document']
      reference.append(r1)


    scores = evaluator.get_scores(hypothesis, reference)


    for metric, results in sorted(scores.items(), key=lambda x: x[0]):
        if not apply_avg and not apply_best: # value is a type of list as we evaluate each summary vs each reference
            for hypothesis_id, results_per_ref in enumerate(results):
                nb_references = len(results_per_ref['p'])
                for reference_id in range(nb_references):
                    print('\tHypothesis #{} & Reference #{}: '.format(hypothesis_id, reference_id))
                    #precision.append(results_per_ref['p'][reference_id])
                    #recall.append(results_per_ref['r'][reference_id])
                    print('\t' + prepare_results(results_per_ref['p'][reference_id], results_per_ref['r'][reference_id], results_per_ref['f'][reference_id]))
            print()
        else:
          #print(prepare_results(results['p'], results['r'], results['f']))
          s1 = s1+ prepare_results(results['p'], results['r'], results['f'])
          s1 = s1+"\n"
          print(s1)

    print()

len(recall)
len(precision)

import matplotlib.pyplot as plt
plt.hist(precision, 10, (0,1), color = 'green',
        histtype = 'bar', rwidth = 0.8)

plt.xlabel('x - axis')
# naming the y axis
plt.ylabel('y - axis')
# giving a title to my graph
plt.title('Histogram of precision')

# show a legend on the plot
plt.legend()

# function to show the plot
plt.show()
display()

with s3.open('insert your S3 bucket path/results.txt','w') as f:
  f.write(s1)

with s3.open('insert your S3 bucket path/results.txt','r') as f:
  a = f.readlines()
a
