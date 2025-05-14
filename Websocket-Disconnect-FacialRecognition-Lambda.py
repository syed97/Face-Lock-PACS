import json
import boto3
import os

#  Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')
CONNECTION_TABLE = os.environ['CONNECTION_TABLE']  # DynamoDB table name

def lambda_handler(event, context):
    try:
        print(f"Received event: {event}")
        print(f"Context: {context}")
        
        # Scan the table to get all items
        response = dynamodb.scan(TableName=CONNECTION_TABLE)
        items = response.get('Items', [])
        
        # If the table is empty, return success
        if not items:
            print("No items found in the table.")
            return {
                'statusCode': 200,
                'body': json.dumps("Table is already empty.")
            }
        
        # Iterate over items and delete them
        for item in items:
            dynamodb.delete_item(
                TableName=CONNECTION_TABLE,
                Key={
                    'CurrentConnection': item['CurrentConnection']  # Primary Key
                }
            )
            print(f"Deleted item: {item['CurrentConnection']}")

        print("All items deleted from the table.")
        return {
            'statusCode': 200,
            'body': json.dumps("Disconnected and all table values cleared.")
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error clearing the table: {str(e)}")
        }
