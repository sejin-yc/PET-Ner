// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from catbot_interfaces:action/VlaTask.idl
// generated code does not contain a copyright notice

#ifndef CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__BUILDER_HPP_
#define CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "catbot_interfaces/action/detail/vla_task__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_Goal_task_type
{
public:
  Init_VlaTask_Goal_task_type()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::catbot_interfaces::action::VlaTask_Goal task_type(::catbot_interfaces::action::VlaTask_Goal::_task_type_type arg)
  {
    msg_.task_type = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_Goal msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_Goal>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_Goal_task_type();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_Result_message
{
public:
  explicit Init_VlaTask_Result_message(::catbot_interfaces::action::VlaTask_Result & msg)
  : msg_(msg)
  {}
  ::catbot_interfaces::action::VlaTask_Result message(::catbot_interfaces::action::VlaTask_Result::_message_type arg)
  {
    msg_.message = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_Result msg_;
};

class Init_VlaTask_Result_success
{
public:
  Init_VlaTask_Result_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VlaTask_Result_message success(::catbot_interfaces::action::VlaTask_Result::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_VlaTask_Result_message(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_Result msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_Result>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_Result_success();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_Feedback_status
{
public:
  Init_VlaTask_Feedback_status()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::catbot_interfaces::action::VlaTask_Feedback status(::catbot_interfaces::action::VlaTask_Feedback::_status_type arg)
  {
    msg_.status = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_Feedback msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_Feedback>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_Feedback_status();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_SendGoal_Request_goal
{
public:
  explicit Init_VlaTask_SendGoal_Request_goal(::catbot_interfaces::action::VlaTask_SendGoal_Request & msg)
  : msg_(msg)
  {}
  ::catbot_interfaces::action::VlaTask_SendGoal_Request goal(::catbot_interfaces::action::VlaTask_SendGoal_Request::_goal_type arg)
  {
    msg_.goal = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_SendGoal_Request msg_;
};

class Init_VlaTask_SendGoal_Request_goal_id
{
public:
  Init_VlaTask_SendGoal_Request_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VlaTask_SendGoal_Request_goal goal_id(::catbot_interfaces::action::VlaTask_SendGoal_Request::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return Init_VlaTask_SendGoal_Request_goal(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_SendGoal_Request msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_SendGoal_Request>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_SendGoal_Request_goal_id();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_SendGoal_Response_stamp
{
public:
  explicit Init_VlaTask_SendGoal_Response_stamp(::catbot_interfaces::action::VlaTask_SendGoal_Response & msg)
  : msg_(msg)
  {}
  ::catbot_interfaces::action::VlaTask_SendGoal_Response stamp(::catbot_interfaces::action::VlaTask_SendGoal_Response::_stamp_type arg)
  {
    msg_.stamp = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_SendGoal_Response msg_;
};

class Init_VlaTask_SendGoal_Response_accepted
{
public:
  Init_VlaTask_SendGoal_Response_accepted()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VlaTask_SendGoal_Response_stamp accepted(::catbot_interfaces::action::VlaTask_SendGoal_Response::_accepted_type arg)
  {
    msg_.accepted = std::move(arg);
    return Init_VlaTask_SendGoal_Response_stamp(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_SendGoal_Response msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_SendGoal_Response>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_SendGoal_Response_accepted();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_GetResult_Request_goal_id
{
public:
  Init_VlaTask_GetResult_Request_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::catbot_interfaces::action::VlaTask_GetResult_Request goal_id(::catbot_interfaces::action::VlaTask_GetResult_Request::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_GetResult_Request msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_GetResult_Request>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_GetResult_Request_goal_id();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_GetResult_Response_result
{
public:
  explicit Init_VlaTask_GetResult_Response_result(::catbot_interfaces::action::VlaTask_GetResult_Response & msg)
  : msg_(msg)
  {}
  ::catbot_interfaces::action::VlaTask_GetResult_Response result(::catbot_interfaces::action::VlaTask_GetResult_Response::_result_type arg)
  {
    msg_.result = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_GetResult_Response msg_;
};

class Init_VlaTask_GetResult_Response_status
{
public:
  Init_VlaTask_GetResult_Response_status()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VlaTask_GetResult_Response_result status(::catbot_interfaces::action::VlaTask_GetResult_Response::_status_type arg)
  {
    msg_.status = std::move(arg);
    return Init_VlaTask_GetResult_Response_result(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_GetResult_Response msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_GetResult_Response>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_GetResult_Response_status();
}

}  // namespace catbot_interfaces


namespace catbot_interfaces
{

namespace action
{

namespace builder
{

class Init_VlaTask_FeedbackMessage_feedback
{
public:
  explicit Init_VlaTask_FeedbackMessage_feedback(::catbot_interfaces::action::VlaTask_FeedbackMessage & msg)
  : msg_(msg)
  {}
  ::catbot_interfaces::action::VlaTask_FeedbackMessage feedback(::catbot_interfaces::action::VlaTask_FeedbackMessage::_feedback_type arg)
  {
    msg_.feedback = std::move(arg);
    return std::move(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_FeedbackMessage msg_;
};

class Init_VlaTask_FeedbackMessage_goal_id
{
public:
  Init_VlaTask_FeedbackMessage_goal_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VlaTask_FeedbackMessage_feedback goal_id(::catbot_interfaces::action::VlaTask_FeedbackMessage::_goal_id_type arg)
  {
    msg_.goal_id = std::move(arg);
    return Init_VlaTask_FeedbackMessage_feedback(msg_);
  }

private:
  ::catbot_interfaces::action::VlaTask_FeedbackMessage msg_;
};

}  // namespace builder

}  // namespace action

template<typename MessageType>
auto build();

template<>
inline
auto build<::catbot_interfaces::action::VlaTask_FeedbackMessage>()
{
  return catbot_interfaces::action::builder::Init_VlaTask_FeedbackMessage_goal_id();
}

}  // namespace catbot_interfaces

#endif  // CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__BUILDER_HPP_
