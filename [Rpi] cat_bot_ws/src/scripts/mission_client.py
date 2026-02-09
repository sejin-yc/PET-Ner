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
        self.last_success = False 

    def send_goal(self, prompt):
        self.done_event.clear()
        self.last_success = False
        self.get_logger().info(f'🚀 [Client] 작업 요청 전송: "{prompt}"')

        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('❌ 서버(Jetson)를 찾을 수 없습니다. 네트워크 설정을 확인하세요.')
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
            self.get_logger().error('❌ 서버가 작업을 거부했습니다.')
            self.done_event.set()
            return

        self.get_logger().info('✅ 서버 승인됨! (로봇 움직이는 중...)')
        self._goal_handle = goal_handle
        
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        # 서버에서 보내주는 상태 메시지 출력 (예: Motion: 150 | TargetMaxErr: 5.0)
        print(f'\r🔄 {feedback.status}', end='', flush=True)

    def get_result_callback(self, future):
        try:
            result = future.result().result
            status = future.result().status
            
            print() # 줄바꿈
            if status == 5: # CANCELED
                self.get_logger().warn('🛑 작업이 취소되었습니다.')
                self.last_success = False
            elif result.success:
                self.get_logger().info(f'🎉 작업 성공! 결과: {result.message}')
                self.last_success = True
            else:
                self.get_logger().error(f'💥 작업 실패: {result.message}')
                self.last_success = False
        except Exception as e:
            self.get_logger().warn(f'결과 처리 중 예외: {e}')
            self.last_success = False
        
        self.done_event.set()

    def cancel_current_goal(self):
        if self._goal_handle is not None:
            self.get_logger().warn('⚠️ 작업 취소 요청 중...')
            future = self._goal_handle.cancel_goal_async()
        else:
            self.get_logger().info('취소할 작업이 없습니다.')
            self.done_event.set()

def get_user_selection():
    # 시퀀스 정의 (화장실 청소 루틴)
    full_toilet_sequence = [
        "Pick up the shovel from the right holder.",
        "Scoop the brown snack from the center box using the shovel.",
        "Move the shovel to the left box and discard the snack.",
        "Return the shovel to the right holder."
    ]

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
        "8": "Return the shovel to the right holder.",
        # [Sequence]
        "9": full_toilet_sequence,
        # [Replay]
        "r": "replay 0" # 예시용
    }

    print("\n========== [ RPi 5 -> Jetson Controller ] ==========")
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
    print(" 🔄 Special:")
    print("  9. 전체 청소 시퀀스 (5->6->7->8)")
    print("  r. 리플레이 테스트 (replay 0)")
    print(" ----------------------------------------------------")
    print("  ⌨️  직접 입력 가능 (예: open gripper, replay 10)")
    print("  q. 종료 (Quit)")
    print("=====================================================")
    
    user_input = input("👉 명령 선택: ").strip()
    
    if not user_input: return ""
    if user_input.lower() == 'q': return None

    if user_input in tasks:
        return tasks[user_input]
    
    return user_input

def main(args=None):
    rclpy.init(args=args)
    controller = MissionController()

    # ROS 통신 스레드 시작
    spin_thread = threading.Thread(target=rclpy.spin, args=(controller,), daemon=True)
    spin_thread.start()

    try:
        while rclpy.ok():
            selected_task = get_user_selection()
            
            if selected_task is None:
                print("👋 클라이언트 종료.")
                break
            
            if not selected_task: continue

            # 리스트(시퀀스)인지 단일 명령인지 확인
            task_list = selected_task if isinstance(selected_task, list) else [selected_task]

            for i, task_prompt in enumerate(task_list):
                if len(task_list) > 1:
                    print(f"\n▶️ [Step {i+1}/{len(task_list)}] 전송: {task_prompt}")
                
                success = controller.send_goal(task_prompt)
                
                if success:
                    try:
                        # 작업 완료될 때까지 대기 (Blocking)
                        controller.done_event.wait()
                        
                        # 시퀀스 모드일 때 실패하면 중단
                        if len(task_list) > 1 and not controller.last_success:
                            print("⛔ 작업 실패로 인해 시퀀스를 중단합니다.")
                            break
                    except KeyboardInterrupt:
                        print("\n🛑 사용자 취소 (Ctrl+C)")
                        controller.cancel_current_goal()
                        controller.done_event.wait()
                        raise KeyboardInterrupt
            
            print("\n✅ 모든 명령 처리 완료.")

    except KeyboardInterrupt:
        print("\n👋 강제 종료")
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
