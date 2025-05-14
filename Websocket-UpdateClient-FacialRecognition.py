import json
import boto3
import os

# Initialize the API Gateway Management API client
WEBSOCKET_URL = os.environ['WEBSOCKET_URL']  # WebSocket endpoint URL
client = boto3.client(
    'apigatewaymanagementapi',
    endpoint_url=WEBSOCKET_URL
)

# Initialize the DynamoDB client
dynamodb = boto3.client('dynamodb')
CONNECTION_TABLE = os.environ['CONNECTION_TABLE']  # DynamoDB table name

def lambda_handler(event, context):
    try:
        # Retrieve the connectionId from DynamoDB
        response = dynamodb.get_item(
            TableName=CONNECTION_TABLE,
            Key={
                'CurrentConnection': {'S': 'active_connection'}
            }
        )
        
        if 'Item' not in response:
            print("No active connection found in the table.")
            return {
                'statusCode': 404,
                'body': json.dumps("No active connection found.")
            }

        connection_id = response['Item']['ConnectionID']['S']
        print(f"Retrieved connectionId from DynamoDB: {connection_id}")

        # Extract the message from the event
        message = event.get("message", "No message provided")
        
        print(f"Attempting to send message to connectionId: {connection_id}")
        
        # Post the message to the WebSocket connection
        response = client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        
        print("Message sent successfully:", response)
        return {
            'statusCode': 200,
            'body': json.dumps("Message sent successfully!")
        }

    except client.exceptions.GoneException:
        # Handle case where the connection is no longer valid
        print(f"ConnectionId {connection_id} is no longer valid (GoneException).")
        return {
            'statusCode': 410,
            'body': json.dumps(f"ConnectionId {connection_id} is no longer valid.")
        }

    except Exception as e:
        # Catch any other errors
        print(f"Failed to send message: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
