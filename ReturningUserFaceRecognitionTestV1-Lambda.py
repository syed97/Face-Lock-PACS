import boto3
import json
import os
from datetime import datetime

# Initialize AWS clients 
rekognition_client = boto3.client('rekognition')
dynamodb_client = boto3.client('dynamodb')
lambda_client = boto3.client('lambda')  # To invoke another Lambda

# Environment variables
BUCKET_NAME = os.environ['BUCKET_NAME']  # Returning users bucket
USER_FACE_COLLECTION = os.environ['USER_FACE_COLLECTION']  # Face collection
DDB_TABLE_NAME = os.environ['DDB_TABLE_NAME']  # User metadata table
LOGIN_DDB_TABLE_NAME = os.environ['LOGIN_DDB_TABLE_NAME']  # Login records table
BROADCAST_LAMBDA_ARN = os.environ['BROADCAST_LAMBDA_ARN']  # ARN of the Broadcast Lambda

def lambda_handler(event, context):
    try:
        # Log the event
        print(f"Event: {json.dumps(event)}")
        
        # Get S3 object details from the event
        s3_object = event['Records'][0]['s3']['object']
        s3_key = s3_object['key']  # S3 object key (uploaded file)
        print(f"Processing image: {s3_key}")
        
        # Rekognition: Search for the face
        response = rekognition_client.search_faces_by_image(
            CollectionId=USER_FACE_COLLECTION,
            Image={
                'S3Object': {
                    'Bucket': BUCKET_NAME,
                    'Name': s3_key
                }
            },
            MaxFaces=1,  # Find the closest match
            FaceMatchThreshold=90  # Adjust confidence threshold as needed
        )
        
        if response['FaceMatches']:
            # Match found
            face_match = response['FaceMatches'][0]
            face_id = face_match['Face']['FaceId']
            confidence = face_match['Similarity']
            
            # Query DynamoDB to get the user ID
            result = dynamodb_client.get_item(
                TableName=DDB_TABLE_NAME,
                Key={'FaceId': {'S': face_id}}
            )
            
            if 'Item' in result:
                user_id = result['Item']['userID']['S']
                print(f"Welcome back, {user_id}! Similarity: {confidence}")
                
                # Log the successful login in the LOGIN_DDB_TABLE_NAME
                login_timestamp = datetime.utcnow().isoformat()
                dynamodb_client.put_item(
                    TableName=LOGIN_DDB_TABLE_NAME,
                    Item={
                        'FaceId': {'S': face_id},  # Primary key
                        'LoginTimestamp': {'S': login_timestamp},  # Sort key
                        'userID': {'S': user_id},  # User ID
                        'BucketLocation': {'S': f"s3://{BUCKET_NAME}/{s3_key}"},  # S3 object location
                        'Event': {'S': 'user-sign-in'}  # Event type
                    }
                )
                print(f"Login record stored for FaceId: {face_id}")

                # Define the message for the Broadcast Lambda
                message = {
                    "userID": user_id,
                    "event": "user-sign-in",
                    "timestamp": login_timestamp
                }

                # Invoke the Broadcast Lambda
                try:
                    invoke_response = lambda_client.invoke(
                        FunctionName=BROADCAST_LAMBDA_ARN,
                        InvocationType='Event',  # Async invocation
                        Payload=json.dumps({"message": message})
                    )
                    print(f"Broadcast Lambda invoked successfully. Response: {invoke_response}")
                except lambda_client.exceptions.ResourceNotFoundException:
                    print("Error: The specified Broadcast Lambda function does not exist.")
                    return {
                        'statusCode': 500,
                        'body': json.dumps("Broadcast Lambda function not found.")
                    }
                except lambda_client.exceptions.InvalidRequestContentException as e:
                    print(f"Error: Invalid request content when invoking the Broadcast Lambda. Details: {str(e)}")
                    return {
                        'statusCode': 500,
                        'body': json.dumps(f"Invalid request content for Broadcast Lambda: {str(e)}")
                    }
                except lambda_client.exceptions.InvalidRuntimeException as e:
                    print(f"Error: Invalid runtime for the Broadcast Lambda. Details: {str(e)}")
                    return {
                        'statusCode': 500,
                        'body': json.dumps(f"Invalid runtime for Broadcast Lambda: {str(e)}")
                    }
                except Exception as e:
                    print(f"Error: Failed to invoke the Broadcast Lambda. Details: {str(e)}")
                    return {
                        'statusCode': 500,
                        'body': json.dumps(f"Unexpected error when invoking Broadcast Lambda: {str(e)}")
                    }

                return {
                    'statusCode': 200,
                    'body': json.dumps(f"Welcome back, {user_id}! Similarity: {confidence}")
                }
            else:
                print("Face recognized but no associated user found in DynamoDB.")
                return {
                    'statusCode': 404,
                    'body': json.dumps("Face recognized but no associated user found in DynamoDB.")
                }
        else:
            # No match found
            login_timestamp = datetime.utcnow().isoformat()
            message = {
                "event": "not-recognized",
                "timestamp": login_timestamp
            }

            # Invoke the Broadcast Lambda
            try:
                invoke_response = lambda_client.invoke(
                    FunctionName=BROADCAST_LAMBDA_ARN,
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps({"message": message})
                )
                print(f"Broadcast Lambda invoked successfully. Response: {invoke_response}")
            except lambda_client.exceptions.ResourceNotFoundException:
                print("Error: The specified Broadcast Lambda function does not exist.")
                return {
                    'statusCode': 500,
                    'body': json.dumps("Broadcast Lambda function not found.")
                }
            except lambda_client.exceptions.InvalidRequestContentException as e:
                print(f"Error: Invalid request content when invoking the Broadcast Lambda. Details: {str(e)}")
                return {
                    'statusCode': 500,
                    'body': json.dumps(f"Invalid request content for Broadcast Lambda: {str(e)}")
                }
            except lambda_client.exceptions.InvalidRuntimeException as e:
                print(f"Error: Invalid runtime for the Broadcast Lambda. Details: {str(e)}")
                return {
                    'statusCode': 500,
                    'body': json.dumps(f"Invalid runtime for Broadcast Lambda: {str(e)}")
                }
            except Exception as e:
                print(f"Error: Failed to invoke the Broadcast Lambda. Details: {str(e)}")
                return {
                    'statusCode': 500,
                    'body': json.dumps(f"Unexpected error when invoking Broadcast Lambda: {str(e)}")
                }

            print("NotRecognized")
            return {
                'statusCode': 404,
                'body': json.dumps("NotRecognized")
            }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
