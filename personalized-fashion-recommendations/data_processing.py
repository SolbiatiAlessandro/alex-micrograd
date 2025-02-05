import pandas as pd
import numpy as np 

def read_data(path="./data"):
    customers = pd.read_csv(path + "customers.csv")
    articles = pd.read_csv(path + "articles.csv")
    transactions = pd.read_csv(path + "transactions_train.csv")
    return customers, articles, transactions

def train_test(transactions, factor=250000):
    # Split the transactions into training and testing sets
    train = transactions[-5*factor:-factor]
    test = transactions[-factor:]

    return train, test

def train_test_no_coldstart(transactions, factor=250000):
    """
    Splits transactions into training and test sets such that:
      - The training set is a contiguous block of 5*factor transactions
        immediately preceding the candidate test pool.
      - The test set is exactly factor rows from the candidate test pool,
        filtered to include only those rows where both the customer_id and
        article_id appear in the training set.
    
    If the candidate test pool does not contain enough valid test rows (after
    filtering), the candidate test pool is expanded backwards (thus shifting the 
    training set earlier) until enough valid test samples are found.
    
    Parameters:
      transactions : pd.DataFrame
          Must have at least "customer_id" and "article_id" columns and be sorted 
          in ascending order by time.
      factor : int, default 250000
          The desired number of test samples.
          
    Returns:
      train : pd.DataFrame
          A block of 5*factor transactions immediately preceding the candidate test pool.
      test : pd.DataFrame
          Exactly factor rows from the candidate test pool (the most recent ones)
          where both customer_id and article_id appear in train.
    
    Raises:
      ValueError if not enough valid test samples can be found.
    """
    n = len(transactions)
    
    # Start with a candidate test pool defined as the last "factor" rows.
    candidate_end = n  # always the end of the DataFrame
    candidate_start = n - factor
    
    # Loop: if after filtering we don't have enough test rows,
    # expand the candidate pool backwards (by one factor at a time).
    while candidate_start >= 5 * factor:
        # Define training as the 5*factor rows immediately preceding the candidate pool.
        train = transactions.iloc[candidate_start - 5 * factor : candidate_start]
        
        # Candidate test pool: transactions from candidate_start to the end.
        candidate_test = transactions.iloc[candidate_start:candidate_end]
        
        # Valid customers and articles are those present in training.
        valid_customers = set(train["customer_id"].unique())
        valid_articles = set(train["article_id"].unique())
        
        # Filter candidate test pool to keep only rows with valid customer_ids and article_ids.
        valid_test = candidate_test[
            candidate_test["customer_id"].isin(valid_customers) &
            candidate_test["article_id"].isin(valid_articles)
        ]
        
        if len(valid_test) >= factor:
            # Take the most recent factor rows from the valid_test pool.
            test = valid_test.iloc[-factor:]
            return train, test
        
        # If not enough valid test samples, expand the candidate pool backwards by factor rows.
        candidate_start -= factor
    
    raise ValueError("Not enough valid test samples available in the data.")




def get_labels_no_coldstart(train_transactions, random_state=None):
    """
    Given training transaction data (with at least columns "customer_id" and "article_id"),
    returns a new DataFrame with columns "customer_id", "article_id", and "label" where:
      - Positive examples (label=1) are the interactions in train_transactions.
      - Negative examples (label=0) are generated by sampling, for each positive example,
        an article (from the set of articles present in training) that the user has not
        interacted with.
    
    The returned DataFrame is balanced 50% positive and 50% negative. If, for a given positive
    sample, no negative candidate exists, that sample is skipped.
    
    Parameters:
      train_transactions (pd.DataFrame): DataFrame with at least "customer_id" and "article_id".
      random_state (int, optional): Seed for reproducibility.
    
    Returns:
      pd.DataFrame: A DataFrame with columns "customer_id", "article_id", and "label", balanced
                    50% positive and 50% negative.
    """
    # Set random seed if provided
    if random_state is not None:
        np.random.seed(random_state)
    
    # Create a DataFrame of positive interactions and assign label=1.
    pos_df = train_transactions[['customer_id', 'article_id']].copy()
    pos_df['label'] = 1
    
    # Build a mapping from user to the set of articles the user has interacted with.
    user_to_articles = pos_df.groupby('customer_id')['article_id'].agg(set).to_dict()
    
    # Create the pool of all articles seen in training.
    all_articles = set(train_transactions['article_id'].unique())
    
    neg_rows = []
    # For each positive interaction, sample one negative example for the same user.
    for _, row in pos_df.iterrows():
        user = row['customer_id']
        # Candidate negatives: articles in training that the user has NOT interacted with.
        candidate_articles = list(all_articles - user_to_articles[user])
        if candidate_articles:
            neg_article = np.random.choice(candidate_articles)
            neg_rows.append({'customer_id': user, 'article_id': neg_article, 'label': 0})
        # If no candidate negatives exist for a user, skip this positive interaction.
    
    neg_df = pd.DataFrame(neg_rows)
    
    # It is possible that we did not generate as many negatives as positives.
    # To ensure a balanced set, we sample from the larger group.
    num_pos = len(pos_df)
    num_neg = len(neg_df)
    
    if num_neg < num_pos:
        # If negatives are fewer, sample the positives down.
        pos_df = pos_df.sample(n=num_neg, random_state=random_state)
    elif num_pos < num_neg:
        # If positives are fewer, sample the negatives down.
        neg_df = neg_df.sample(n=num_pos, random_state=random_state)
    
    # Combine the positive and negative examples.
    labeled_df = pd.concat([pos_df, neg_df], ignore_index=True)
    # Shuffle the final DataFrame.
    labeled_df = labeled_df.sample(frac=1, random_state=random_state).reset_index(drop=True)
    
    return labeled_df

    
    
