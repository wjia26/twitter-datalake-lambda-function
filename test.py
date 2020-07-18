import os
import json
import boto3
import s3fs
import pandas as pd
import tweepy
import json
from datetime import datetime
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer as SIA

# ACCESS_TOKEN_1 = os.environ['ACCESS_TOKEN_1']
# ACCESS_TOKEN_SECRET_1 = os.environ['ACCESS_TOKEN_SECRET_1']
# CONSUMER_KEY_1 = os.environ['CONSUMER_KEY_1']
# CONSUMER_SECRET_1 = os.environ['CONSUMER_SECRET_1']   
# ACCESS_TOKEN_2 = os.environ['ACCESS_TOKEN_2']
# ACCESS_TOKEN_SECRET_2 = os.environ['ACCESS_TOKEN_SECRET_2']
# CONSUMER_KEY_2 = os.environ['CONSUMER_KEY_2']
# CONSUMER_SECRET_2 = os.environ['CONSUMER_SECRET_2'] 
# ACCESS_TOKEN_3 = os.environ['ACCESS_TOKEN_3']
# ACCESS_TOKEN_SECRET_3 = os.environ['ACCESS_TOKEN_SECRET_3']
# CONSUMER_KEY_3 = os.environ['CONSUMER_KEY_3']
# CONSUMER_SECRET_3 = os.environ['CONSUMER_SECRET_3']  
# AWS_ACCESS_KEY_ID=os.environ['AWS_ACCESS_KEY_ID']
# AWS_ACCESS_KEY_SECRET=os.environ['AWS_ACCESS_KEY_SECRET']



def polarity(row):
    #Does the sentiment analysis stuff
    vader_path=os.getcwd()+'/nltk_data/sentiment/vader_lexicon.zip/vader_lexicon/vader_lexicon.txt'
    sia = SIA(lexicon_file=vader_path)
    polarity=sia.polarity_scores(row)
    return polarity['compound']

def run_etl(fs):
    with fs.open('s3://mykeysandstuff/query_list.csv', 'r') as f1:
        df_query_list=pd.read_csv(f1)
    #Read the state from the list
    with fs.open('s3://mykeysandstuff/index_state.json', 'r') as f2:
        index_state_json = json.load(f2)
        index=index_state_json["index_state"]

    #Rotates the key's depending on the index you're on. So that we don't hit the rate limit.
    if index%3==0:
        append_str='_1'
    elif index%3==1:
        append_str='_2'
    else:
        append_str='_3'   
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(os.environ["CONSUMER_KEY" + append_str], os.environ["CONSUMER_SECRET" + append_str])
    auth.set_access_token(os.environ["ACCESS_TOKEN" + append_str], os.environ["ACCESS_TOKEN_SECRET" + append_str])
    api = tweepy.API(auth)
     
    #select the row with index of the state
    row=df_query_list.loc[index]
    print(row)
    search_id_list=[]
    try:
        for file in fs.listdir('twitterdatalake'):
            file_key=file['Key']
            if ".parquet" in file_key and row['file_name'] in file_key and row['category'] in file_key:
                search_id=file_key.split('-')[1]
                search_id_list.append(search_id)

        if not search_id_list:
            last_since_id=None
        else:
            last_since_id=max(search_id_list)
        
        print(last_since_id)

        #Get Search Results
        search_results=tweepy.Cursor(api.search,q=row['search'], lang="en",since_id=last_since_id, tweet_mode='extended').items(1000) #since_id neeeded here at some point
        rows_list=[]
        for tweet in search_results:
            dict1 = {}
            dict1['twitter_id']=tweet.id
            dict1['username']=tweet.user.name
            dict1['screenname']=tweet.user.screen_name
            dict1['text']=tweet.full_text
            dict1['created_at']=tweet.created_at
            dict1['retweet_count']=tweet.retweet_count
            dict1['location']=tweet.user.location
            dict1['followers']=tweet.user.followers_count
            dict1['friends']=tweet.user.friends_count
            dict1['search_query']=row['search']
            dict1['file_name']=row['file_name']
            dict1['group_name']=row['group_name']
            rows_list.append(dict1)

        #Increment the state and make sure it will loop back next round
        index_state_json['index_state']=(index+1)%len(df_query_list)
        print(index_state_json['index_state'])
        with fs.open('s3://mykeysandstuff/index_state.json', 'w') as outfile:
            json.dump(index_state_json, outfile)
            print(index_state_json)
        
        #output to dataframe and then to snappy.parquet form
        df=pd.DataFrame(rows_list) 
        if len(df)==0:
            return row['file_name'],len(df)
        file_dir='s3://twitterdatalake/'
        df['polarity']=df['text'].apply(polarity)
        to_csv_timestamp = datetime.today().strftime('%Y%m%d_%H%M%S')
        max_twitter_id=max(df['twitter_id'])
        full_filename=file_dir+row['category'] +'/'+ row['file_name'] +'/'+  to_csv_timestamp + '-' + str(max_twitter_id)
        with fs.open(full_filename+ '.csv','w', encoding="utf-8", newline = '\n') as f:
            df = df.replace('\n',' ', regex=True)
            df.to_csv(f, index=False)
    #     with fs.open(full_filename+ '.snappy.parquet','w', encoding="utf-8") as f:
    #         df.to_parquet(f,compression='SNAPPY')




        return row['file_name'],len(df)

    
    except Exception as e:
        print('Exception here:' + str(e))

def lambda_handler(event, context):

    #Auth to s3fs
    fs = s3fs.S3FileSystem(anon=False)

    #Run ETL job
    file_name,numberOfRows=run_etl(fs)

    
    return {
        'statusCode': 200,
        'file_name': file_name,
        'number_of_rows': numberOfRows
    }
