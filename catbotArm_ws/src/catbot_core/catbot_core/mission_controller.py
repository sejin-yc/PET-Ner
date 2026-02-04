import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from catbot_interfaces.action import VlaTask
import sys
import threading

class MissionController(Node):
    def __init__(self):
        super().__init__('mission_controller')
        self._action_client = ActionClient(self, VlaTask, 'execute_vla_task')
        self._goal_handle = None
        self.done_event = threading.Event()

    def send_goal(self, prompt):
        self.done_event.clear()
        self.get_logger().info(f'🚀 VLA 작업 요청: "{prompt}"')
        
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('❌ 서버를 찾을 수 없습니다.')
            self.done_event.set()
            return False

        goal_msg = VlaTask.Goal()
        goal_msg.task_type = prompt

        self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)
        return True

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('❌ 작업 거부됨')
            self.done_event.set()
            return

        self.get_logger().info('✅ 작업 수락됨! (실행 중...)')
        self._goal_handle = goal_handle
        
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        # 줄바꿈 없이 한 줄로 상태 업데이트
        print(f'\r🔄 {feedback.status}', end='', flush=True)

    def get_result_callback(self, future):
        try:
            result = future.result().result
            status = future.result().status
            
            print() # 줄바꿈
            if status == 5: # CANCELED
                self.get_logger().warn('🛑 작업이 취소되었습니다.')
            elif result.success:
                self.get_logger().info(f'🎉 작업 완료! 결과: {result.message}')
            else:
                self.get_logger().error(f'💥 작업 실패: {result.message}')
        except Exception as e:
            self.get_logger().warn(f'결과 처리 중 예외: {e}')
        
        self.done_event.set()

    def cancel_current_goal(self):
        if self._goal_handle is not None:
            self.get_logger().warn('⚠️ 작업 취소 요청 중...')
            future = self._goal_handle.cancel_goal_async()
        else:
            self.get_logger().info('취소할 작업이 없습니다.')
            self.done_event.set()

def get_user_selection():
    """번호를 누르면 프리셋 실행, 텍스트를 치면 커스텀 실행"""
    tasks = {
        # [Water Task]
        "1": "Pick up the clear plastic water cup",
        "2": "Pour out the water from the cup",
        "3": "Place the cup under the dispenser",
        "4": "place the cup on the floor",
        # [Toilet Task]
        "5": "Pick up the shovel from the right holder.",
        "6": "Scoop the brown snack from the center box using the shovel.",
        "7": "Move the shovel to the left box and discard the snack.",
        "8": "Return the shovel to the right holder."
    }

    print("\n========== [ Catbot Mission Menu ] ==========")
    print(" 💧 Water Tasks:")
    print("  1. 컵 집기 (Pick up)")
    print("  2. 물 붓기 (Pour water)")
    print("  3. 물 받기 (Dispenser)")
    print("  4. 내려놓기 (Place floor)")
    print(" 🚽 Toilet Tasks:")
    print("  5. 삽 집기 (Pick shovel)")
    print("  6. 똥 푸기 (Scoop snack)")
    print("  7. 버리기 (Discard)")
    print("  8. 삽 반납 (Return shovel)")
    print(" --------------------------------------------")
    print("  ⌨️  직접 입력 가능 (예: open gripper)")
    print("  q. 종료 (Quit)")
    print("=============================================")
    
    user_input = input("👉 번호 또는 명령어를 입력하세요: ").strip()
    
    if not user_input: # 엔터만 쳤을 때
        return "" # 무시하고 재루프

    if user_input.lower() == 'q':
        return None

    # 1. 번호 리스트에 있으면 해당 문장 반환
    if user_input in tasks:
        return tasks[user_input]
    
    # 2. 없으면 입력한 텍스트 그대로 반환 (커스텀 입력)
    return user_input

def main(args=None):
    rclpy.init(args=args)
    controller = MissionController()

    spin_thread = threading.Thread(target=rclpy.spin, args=(controller,), daemon=True)
    spin_thread.start()

    try:
        while rclpy.ok():
            selected_task = get_user_selection()
            
            # 종료 조건
            if selected_task is None:
                print("👋 프로그램을 종료합니다.")
                break
            
            # 빈 입력(엔터) 무시
            if not selected_task:
                continue

            # 작업 전송
            success = controller.send_goal(selected_task)
            
            if success:
                try:
                    controller.done_event.wait() 
                except KeyboardInterrupt:
                    controller.cancel_current_goal()
                    controller.done_event.wait()
            
            print("\n----------------------------------")
            print("다음 명령을 준비합니다...")

    except KeyboardInterrupt:
        print("\n👋 강제 종료")
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()