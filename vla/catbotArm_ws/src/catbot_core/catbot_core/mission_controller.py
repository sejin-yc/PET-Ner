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
        # [추가] 마지막 작업 성공 여부 저장
        self.last_success = False 

    def send_goal(self, prompt):
        self.done_event.clear()
        self.last_success = False # 초기화
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
                self.get_logger().info(f'🎉 작업 완료! 결과: {result.message}')
                self.last_success = True # [성공 표시]
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
    """번호를 누르면 프리셋(또는 리스트) 실행, 텍스트를 치면 커스텀 실행"""
    
    # [수정] 9번 메뉴에 리스트 형태로 시퀀스 정의
    full_toilet_sequence = [
        "Pick up the shovel from the right holder.",
        "replay 0",
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
        "9": full_toilet_sequence  # 리스트를 값으로 가짐
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
    print(" 🔄 Sequence:")
    print("  9. 전체 청소 실행 (5 -> 6 -> 7 -> 8 연속 실행)")
    print(" --------------------------------------------")
    print("  ⌨️  직접 입력 가능 (예: open gripper)")
    print("  q. 종료 (Quit)")
    print("=============================================")
    
    user_input = input("👉 번호 또는 명령어를 입력하세요: ").strip()
    
    if not user_input:
        return "" 

    if user_input.lower() == 'q':
        return None

    if user_input in tasks:
        return tasks[user_input]
    
    return user_input

def main(args=None):
    rclpy.init(args=args)
    controller = MissionController()

    spin_thread = threading.Thread(target=rclpy.spin, args=(controller,), daemon=True)
    spin_thread.start()

    try:
        while rclpy.ok():
            selected_task = get_user_selection()
            
            if selected_task is None:
                print("👋 프로그램을 종료합니다.")
                break
            
            if not selected_task:
                continue

            # [핵심 수정] 입력값이 리스트인지 확인하여 처리
            # 리스트면 시퀀스 실행, 문자열이면 단일 실행
            
            task_list = []
            if isinstance(selected_task, list):
                print(f"📋 시퀀스 모드: 총 {len(selected_task)}개의 작업을 순차 실행합니다.")
                task_list = selected_task
            else:
                task_list = [selected_task] # 문자열을 리스트로 감싸서 처리

            # 리스트에 있는 모든 작업을 순서대로 실행
            for i, task_prompt in enumerate(task_list):
                if len(task_list) > 1:
                    print(f"\n[Step {i+1}/{len(task_list)}] 실행 중: {task_prompt}")
                
                success = controller.send_goal(task_prompt)
                
                if success:
                    try:
                        controller.done_event.wait() # 작업 완료 대기
                        
                        # [중요] 시퀀스 실행 중 실패하면 즉시 중단
                        if len(task_list) > 1 and not controller.last_success:
                            print("⛔ 이전 작업 실패로 인해 시퀀스를 중단합니다.")
                            break
                            
                    except KeyboardInterrupt:
                        print("\n🛑 사용자 중단 요청!")
                        controller.cancel_current_goal()
                        controller.done_event.wait()
                        raise KeyboardInterrupt # 메인 루프 탈출용
            
            print("\n----------------------------------")
            print("모든 명령 처리 완료. 대기 중...")

    except KeyboardInterrupt:
        print("\n👋 강제 종료")
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()