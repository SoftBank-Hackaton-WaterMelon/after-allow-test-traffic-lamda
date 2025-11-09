import json
import os
import urllib.request
import logging
import boto3

# --- 로깅 및 Boto3 클라이언트 초기화 ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

codedeploy = boto3.client('codedeploy')
dynamodb = boto3.resource('dynamodb') 

def lambda_handler(event, context):
    """
    CodeDeploy의 'AfterAllowTestTraffic' 훅에 의해 트리거됩니다.
    1. 배포 정보를 DynamoDB에 저장합니다.
    2. 테스트 환경 준비 완료 알림을 Slack으로 전송합니다.
    """
    logger.info(f"CodeDeploy 이벤트 수신: {json.dumps(event)}")
    
    # --- 1. 필수 환경 변수 로드 ---
    try:
        slack_url = os.environ['SLACK_WEBHOOK_URL']
        test_url = os.environ['TEST_URL']
        table_name = os.environ['DYNAMODB_TABLE_NAME']
    except KeyError as e:
        logger.error(f"필수 환경 변수가 없습니다: {e}")
        raise Exception(f"환경 변수 누락: {e}")
        
    # --- 2. CodeDeploy 이벤트에서 ID 추출 ---
    try:
        deployment_id = event['DeploymentId']
        hook_execution_id = event['LifecycleEventHookExecutionId']
        logger.info(f"Deployment ID: {deployment_id}")
        logger.info(f"Hook Execution ID: {hook_execution_id}")
    except KeyError:
        logger.error("이벤트에서 'DeploymentId' 또는 'LifecycleEventHookExecutionId'를 찾을 수 없습니다.")
        raise Exception("Invalid CodeDeploy event: Missing IDs")

    # --- 3. DynamoDB에 배포 정보 저장 ---
    try:
        table = dynamodb.Table(table_name)
        table.put_item(
            Item={
                'deployment_id': deployment_id,        
                'hook_execution_id': hook_execution_id
            }
        )
        logger.info(f"배포 정보 ({deployment_id})를 DynamoDB 테이블({table_name})에 성공적으로 저장했습니다.")
    except Exception as e:
        logger.error(f"DynamoDB 저장 실패: {e}")
        raise Exception(f"DynamoDB put_item 실패: {e}")

    # --- 4. Slack 메시지 구성 (이모지 수정됨) ---
    slack_message = {
        # ✅ (u+2705)
        "text": f"✅ ECS 그린 환경 배포 준비 완료 (배포 ID: {deployment_id})",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    # ✅ (u+2705)
                    "text": "✅ ECS 배포: 테스트 대기 중",
                    "emoji": True 
                }
            },
            {
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": "테스트 환경에서 새 버전이 잘 작동하는지 확인해 주세요!\n「テスト環境で新しいバージョンがちゃんと動くか、確認お願いします〜！」"
                }
            },
            {
              "type": "image",
              "image_url": "https://github.com/SoftBank-Hackaton-WaterMelon/Chiikawa/blob/main/wait_for_tests.gif?raw=true",
              "alt_text": "Success - Thumbs up dog"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Deployment ID:*\n`{deployment_id}`"
                    },
                    {
                        "type": "mrkdwn",
                        # [!!!] 수정된 부분: <{test_url}> 로 링크를 닫고 f-string의 " 를 추가했습니다.
                        "text": f"*테스트 URL 🧪:*\n<{test_url}>"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "테스트 완료 후, 아래의 명령어로 배포를 완료해주세요!\n「テスト完了後、以下のコマンドでデプロイを完了してください」\n"
                }
            },
            {
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": f"👉 `/platform-deploy-approve {deployment_id}`"
                }
            }
        ]
    }
    
    # --- 5. Slack 알림 전송 ---
    try:
        payload_str = json.dumps(slack_message, ensure_ascii=False)
        
        payload_bytes = payload_str.encode('utf-8')
        
        req = urllib.request.Request(
            slack_url,
            data=payload_bytes,
            headers={
                'Content-Type': 'application/json' 
            }
        )
        with urllib.request.urlopen(req) as response:
            logger.info(f"Slack 알림 전송 성공. 응답: {response.read().decode('utf-8')}")
        
        return {
            'statusCode': 200,
            'body': '알림 전송 및 DB 저장 성공'
        }
    except urllib.error.HTTPError as e:
        logger.error(f"Slack API 오류 (HTTP): {e.code} {e.read().decode()}")
        raise Exception("Slack 알림 전송에 실패했습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise Exception(f"알림 람다 실행 중 오류 발생: {e}")
