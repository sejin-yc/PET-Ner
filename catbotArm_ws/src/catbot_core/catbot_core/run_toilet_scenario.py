import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from catbot_interfaces.action import VlaTask
import time

class ToiletScenarioClient(Node):
    def __init__(self):
        super().__init__('toilet_scenario_client')
        self._action_client = ActionClient(self, VlaTask, 'execute_vla_task')

    def send_task(self, task_text):
        """액션 서버에 작업을 요청하고 완료될 때까지 기다립니다 (동기 방식)"""
        self.get_logger().info(f'\n🚀 [요청] "{task_text}"')

        # 1. 서버 연결 대기
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('❌ 서버를 찾을 수 없습니다. vla_action_server가 켜져 있나요?')
            return False

        # 2. 목표 전송
        goal_msg = VlaTask.Goal()
        goal_msg.task_type = task_text
        
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error('❌ 작업이 거부되었습니다.')
            return False

        self.get_logger().info('⏳ 작업 수행 중...')

        # 3. 결과 대기
        get_result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, get_result_future)
        
        result = get_result_future.result().result
        status = get_result_future.result().status

        if result.success:
            self.get_logger().info(f'✅ [성공] {task_text}')
            return True
        else:
            self.get_logger().error(f'❌ [실패] {task_text} (메시지: {result.message})')
            return False

def main(args=None):
    rclpy.init(args=args)
    client = ToiletScenarioClient()

    # ==========================================================
    # 🚽 고양이 화장실 청소 시나리오 (순서대로 실행)
    # ==========================================================
    tasks = [
        # 1. 삽 집기 -> [Ready] 자세에서 종료됨
        "Pick up the shovel from the right holder.",
        
        # 2. 똥 푸기 -> [Middle] 자세(들기)에서 종료됨
        "Scoop the brown snack from the center box using the shovel.",1
        
        # 3. 버리기 -> [Middle] 자세(버리고 다시 들기)에서 종료됨
        "Move the shovel to the left box and discard the snack.",
        
        # 4. 제자리 -> [Start] 자세(원위치)에서 종료됨
        "Return the shovel to the right holder."
    ]

    try:
        for i, task in enumerate(tasks):
            print(f"\n--- [Step {i+1}/{len(tasks)}] ---")
            
            # 작업 요청 및 결과 대기
            success = client.send_task(task)
            
            if not success:
                print("⛔ 시나리오 중단: 이전 작업이 실패했습니다.")
                break
            
            # 다음 작업 전 약간의 대기 (로봇 안정화)
            if i < len(tasks) - 1:
                time.sleep(2.0)
        
        if success:
            print("\n🎉 모든 시나리오가 성공적으로 완료되었습니다!")

    except KeyboardInterrupt:
        print("\n강제 종료됨")
    
    finally:
        client.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()