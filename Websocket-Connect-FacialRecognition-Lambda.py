import json
import os
import boto3

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Get the table name from the environment variable
CONNECTION_TABLE = os.environ['CONNECTION_TABLE']

def lambda_handler(event, context):
    try:
        # Extract the connectionId from the event
        connection_id = event['requestContext']['connectionId']
        print(f"Received connectionId: {connection_id}")

        # Write the connectionId to the DynamoDB table
        dynamodb.put_item(
            TableName=CONNECTION_TABLE,
            Item={
                'CurrentConnection': {'S': 'active_connection'},  # Static partition key
                'ConnectionID': {'S': connection_id}              # The connection ID
            }
        )
        print(f"Connection ID {connection_id} written to table {CONNECTION_TABLE}")

        # Return a success response
        return {
            'statusCode': 200,
            'body': json.dumps('Connection Successful!')
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error writing connectionId to DynamoDB: {str(e)}")
        }
