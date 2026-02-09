// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from catbot_interfaces:action/VlaTask.idl
// generated code does not contain a copyright notice

#ifndef CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__STRUCT_H_
#define CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'task_type'
#include "rosidl_runtime_c/string.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_Goal
{
  rosidl_runtime_c__String task_type;
} catbot_interfaces__action__VlaTask_Goal;

// Struct for a sequence of catbot_interfaces__action__VlaTask_Goal.
typedef struct catbot_interfaces__action__VlaTask_Goal__Sequence
{
  catbot_interfaces__action__VlaTask_Goal * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_Goal__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'message'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_Result
{
  bool success;
  rosidl_runtime_c__String message;
} catbot_interfaces__action__VlaTask_Result;

// Struct for a sequence of catbot_interfaces__action__VlaTask_Result.
typedef struct catbot_interfaces__action__VlaTask_Result__Sequence
{
  catbot_interfaces__action__VlaTask_Result * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_Result__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'status'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_Feedback
{
  rosidl_runtime_c__String status;
} catbot_interfaces__action__VlaTask_Feedback;

// Struct for a sequence of catbot_interfaces__action__VlaTask_Feedback.
typedef struct catbot_interfaces__action__VlaTask_Feedback__Sequence
{
  catbot_interfaces__action__VlaTask_Feedback * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_Feedback__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
#include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'goal'
#include "catbot_interfaces/action/detail/vla_task__struct.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_SendGoal_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
  catbot_interfaces__action__VlaTask_Goal goal;
} catbot_interfaces__action__VlaTask_SendGoal_Request;

// Struct for a sequence of catbot_interfaces__action__VlaTask_SendGoal_Request.
typedef struct catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence
{
  catbot_interfaces__action__VlaTask_SendGoal_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'stamp'
#include "builtin_interfaces/msg/detail/time__struct.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_SendGoal_Response
{
  bool accepted;
  builtin_interfaces__msg__Time stamp;
} catbot_interfaces__action__VlaTask_SendGoal_Response;

// Struct for a sequence of catbot_interfaces__action__VlaTask_SendGoal_Response.
typedef struct catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence
{
  catbot_interfaces__action__VlaTask_SendGoal_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_GetResult_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
} catbot_interfaces__action__VlaTask_GetResult_Request;

// Struct for a sequence of catbot_interfaces__action__VlaTask_GetResult_Request.
typedef struct catbot_interfaces__action__VlaTask_GetResult_Request__Sequence
{
  catbot_interfaces__action__VlaTask_GetResult_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_GetResult_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'result'
// already included above
// #include "catbot_interfaces/action/detail/vla_task__struct.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_GetResult_Response
{
  int8_t status;
  catbot_interfaces__action__VlaTask_Result result;
} catbot_interfaces__action__VlaTask_GetResult_Response;

// Struct for a sequence of catbot_interfaces__action__VlaTask_GetResult_Response.
typedef struct catbot_interfaces__action__VlaTask_GetResult_Response__Sequence
{
  catbot_interfaces__action__VlaTask_GetResult_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_GetResult_Response__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'feedback'
// already included above
// #include "catbot_interfaces/action/detail/vla_task__struct.h"

/// Struct defined in action/VlaTask in the package catbot_interfaces.
typedef struct catbot_interfaces__action__VlaTask_FeedbackMessage
{
  unique_identifier_msgs__msg__UUID goal_id;
  catbot_interfaces__action__VlaTask_Feedback feedback;
} catbot_interfaces__action__VlaTask_FeedbackMessage;

// Struct for a sequence of catbot_interfaces__action__VlaTask_FeedbackMessage.
typedef struct catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence
{
  catbot_interfaces__action__VlaTask_FeedbackMessage * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__STRUCT_H_
