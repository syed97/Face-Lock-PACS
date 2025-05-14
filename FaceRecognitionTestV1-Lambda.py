import boto3
import json
import os
from datetime import datetime

# Initialize AWS clients
rekognition_client = boto3.client('rekognition')
dynamodb_client = boto3.client('dynamodb')
lambda_client = boto3.client('lambda')  # To invoke another Lambda

# Environment variables
BUCKET_NAME = os.environ['BUCKET_NAME']
DDB_TABLE_NAME = os.environ['DDB_TABLE_NAME']  # Original user-faceprints table
LOGIN_DDB_TABLE_NAME = os.environ['LOGIN_DDB_TABLE_NAME']  # Login records table
USER_FACE_COLLECTION = os.environ['USER_FACE_COLLECTION']
BROADCAST_LAMBDA_ARN = os.environ['BROADCAST_LAMBDA_ARN']  # ARN of the Broadcast Lambda

def lambda_handler(event, context):
    try:
        # Log the event
        print(f"Event: {json.dumps(event)}")
        
        # Get S3 object details from the event
        s3_object = event['Records'][0]['s3']['object']
        s3_key = s3_object['key']  # Full S3 key (e.g., "uploads/YusefAlimamBlackRing1123.png")
        
        # Extract the file name to use as ExternalImageId (e.g., "YusefAlimamBlackRing1123.png")
        image_name = os.path.basename(s3_key)
        print(f"Processing image: {image_name}")
        
        # Rekognition: Index the face
        response = rekognition_client.index_faces(
            CollectionId=USER_FACE_COLLECTION,  # Replace with your Face Collection
            Image={
                'S3Object': {
                    'Bucket': BUCKET_NAME,
                    'Name': s3_key
                }
            },
            ExternalImageId=image_name,  # Valid ExternalImageId (file name)
            MaxFaces=1,  # Only index the first face
            QualityFilter='AUTO',
            DetectionAttributes=['DEFAULT']
        )
        
        # Extract FaceId and metadata
        if response['FaceRecords']:
            face_record = response['FaceRecords'][0]
            face_id = face_record['Face']['FaceId']
            bounding_box = face_record['Face']['BoundingBox']
            confidence = face_record['Face']['Confidence']
            
            print(f"Face indexed successfully: FaceId={face_id}")
            
            # Current timestamp for login table
            login_timestamp = datetime.utcnow().isoformat()
            
            # DynamoDB: Store face metadata in the user-faceprints table
            dynamodb_client.put_item(
                TableName=DDB_TABLE_NAME,
                Item={
                    'FaceId': {'S': face_id},  # Primary key
                    'userID': {'S': image_name},  # Store user ID as an attribute
                    'BoundingBox': {'S': json.dumps(bounding_box)},
                    'Confidence': {'N': str(confidence)}
                }
            )
            print(f"Metadata stored in {DDB_TABLE_NAME} for FaceId: {face_id}")
            
            # DynamoDB: Write to login records table
            dynamodb_client.put_item(
                TableName=LOGIN_DDB_TABLE_NAME,
                Item={
                    'FaceId': {'S': face_id},  # Primary key
                    'LoginTimestamp': {'S': login_timestamp},  # Sort key
                    'userID': {'S': image_name},  # Additional attribute
                    'BucketLocation': {'S': f"s3://{BUCKET_NAME}/{s3_key}"},  # S3 object location
                    'Event': {'S': 'user-sign-up'}  # Event field
                }
            )
            print(f"Login record stored in {LOGIN_DDB_TABLE_NAME} for FaceId: {face_id}")

            # Define the message for the Broadcast Lambda
            message = {
                "userID": image_name,
                "event": "user-sign-up",
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
                'body': json.dumps(f"User {image_name} indexed successfully and login recorded.")
            }
        else:
            print("No faces detected in the image.")
            return {
                'statusCode': 400,
                'body': json.dumps("No faces detected in the image.")
            }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
