import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from catbot_interfaces.action import VlaTask

class MissionController(Node):
    def __init__(self):
        super().__init__('mission_controller')
        self._action_client = ActionClient(self, VlaTask, 'execute_vla_task')

    def send_goal(self, prompt):
        self.get_logger().info(f'🚀 VLA 작업 요청: "{prompt}"')
        self._action_client.wait_for_server()

        goal_msg = VlaTask.Goal()
        goal_msg.task_type = prompt

        self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('❌ 작업 거부됨')
            return

        self.get_logger().info('✅ 작업 수락됨! 실행 중...')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg):
        # 실행 중 상태 피드백 출력
        feedback = feedback_msg.feedback
        self.get_logger().info(f'🔄 [VLA 상태]: {feedback.status}')

    def get_result_callback(self, future):
        result = future.result().result
        if result.success:
            self.get_logger().info(f'🎉 작업 완료! 메시지: {result.message}')
            # [TODO] 여기에 다음 미션(Nav2 이동 등) 코드 추가
        else:
            self.get_logger().error(f'💥 작업 실패: {result.message}')
        
        # 데모용 종료
        rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    controller = MissionController()
    
    # 예시: 작업 요청 보내기
    task = "Pick up the shovel on the right, scoop the brown snack from the center box, and move it to the left box."
    controller.send_goal(task)
    
    rclpy.spin(controller)

if __name__ == '__main__':
    main()