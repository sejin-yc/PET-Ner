// generated from rosidl_generator_c/resource/idl__functions.h.em
// with input from catbot_interfaces:action/VlaTask.idl
// generated code does not contain a copyright notice

#ifndef CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__FUNCTIONS_H_
#define CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__FUNCTIONS_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stdlib.h>

#include "rosidl_runtime_c/visibility_control.h"
#include "catbot_interfaces/msg/rosidl_generator_c__visibility_control.h"

#include "catbot_interfaces/action/detail/vla_task__struct.h"

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_Goal
 * )) before or use
 * catbot_interfaces__action__VlaTask_Goal__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__init(catbot_interfaces__action__VlaTask_Goal * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Goal__fini(catbot_interfaces__action__VlaTask_Goal * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_Goal__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Goal *
catbot_interfaces__action__VlaTask_Goal__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Goal__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Goal__destroy(catbot_interfaces__action__VlaTask_Goal * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__are_equal(const catbot_interfaces__action__VlaTask_Goal * lhs, const catbot_interfaces__action__VlaTask_Goal * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__copy(
  const catbot_interfaces__action__VlaTask_Goal * input,
  catbot_interfaces__action__VlaTask_Goal * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_Goal__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__Sequence__init(catbot_interfaces__action__VlaTask_Goal__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Goal__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Goal__Sequence__fini(catbot_interfaces__action__VlaTask_Goal__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_Goal__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Goal__Sequence *
catbot_interfaces__action__VlaTask_Goal__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Goal__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Goal__Sequence__destroy(catbot_interfaces__action__VlaTask_Goal__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__Sequence__are_equal(const catbot_interfaces__action__VlaTask_Goal__Sequence * lhs, const catbot_interfaces__action__VlaTask_Goal__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Goal__Sequence__copy(
  const catbot_interfaces__action__VlaTask_Goal__Sequence * input,
  catbot_interfaces__action__VlaTask_Goal__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_Result
 * )) before or use
 * catbot_interfaces__action__VlaTask_Result__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__init(catbot_interfaces__action__VlaTask_Result * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Result__fini(catbot_interfaces__action__VlaTask_Result * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_Result__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Result *
catbot_interfaces__action__VlaTask_Result__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Result__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Result__destroy(catbot_interfaces__action__VlaTask_Result * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__are_equal(const catbot_interfaces__action__VlaTask_Result * lhs, const catbot_interfaces__action__VlaTask_Result * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__copy(
  const catbot_interfaces__action__VlaTask_Result * input,
  catbot_interfaces__action__VlaTask_Result * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_Result__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__Sequence__init(catbot_interfaces__action__VlaTask_Result__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Result__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Result__Sequence__fini(catbot_interfaces__action__VlaTask_Result__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_Result__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Result__Sequence *
catbot_interfaces__action__VlaTask_Result__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Result__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Result__Sequence__destroy(catbot_interfaces__action__VlaTask_Result__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__Sequence__are_equal(const catbot_interfaces__action__VlaTask_Result__Sequence * lhs, const catbot_interfaces__action__VlaTask_Result__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Result__Sequence__copy(
  const catbot_interfaces__action__VlaTask_Result__Sequence * input,
  catbot_interfaces__action__VlaTask_Result__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_Feedback
 * )) before or use
 * catbot_interfaces__action__VlaTask_Feedback__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__init(catbot_interfaces__action__VlaTask_Feedback * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Feedback__fini(catbot_interfaces__action__VlaTask_Feedback * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_Feedback__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Feedback *
catbot_interfaces__action__VlaTask_Feedback__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Feedback__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Feedback__destroy(catbot_interfaces__action__VlaTask_Feedback * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__are_equal(const catbot_interfaces__action__VlaTask_Feedback * lhs, const catbot_interfaces__action__VlaTask_Feedback * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__copy(
  const catbot_interfaces__action__VlaTask_Feedback * input,
  catbot_interfaces__action__VlaTask_Feedback * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_Feedback__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__Sequence__init(catbot_interfaces__action__VlaTask_Feedback__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Feedback__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Feedback__Sequence__fini(catbot_interfaces__action__VlaTask_Feedback__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_Feedback__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_Feedback__Sequence *
catbot_interfaces__action__VlaTask_Feedback__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_Feedback__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_Feedback__Sequence__destroy(catbot_interfaces__action__VlaTask_Feedback__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__Sequence__are_equal(const catbot_interfaces__action__VlaTask_Feedback__Sequence * lhs, const catbot_interfaces__action__VlaTask_Feedback__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_Feedback__Sequence__copy(
  const catbot_interfaces__action__VlaTask_Feedback__Sequence * input,
  catbot_interfaces__action__VlaTask_Feedback__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_SendGoal_Request
 * )) before or use
 * catbot_interfaces__action__VlaTask_SendGoal_Request__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__init(catbot_interfaces__action__VlaTask_SendGoal_Request * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Request__fini(catbot_interfaces__action__VlaTask_SendGoal_Request * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_SendGoal_Request *
catbot_interfaces__action__VlaTask_SendGoal_Request__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Request__destroy(catbot_interfaces__action__VlaTask_SendGoal_Request * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__are_equal(const catbot_interfaces__action__VlaTask_SendGoal_Request * lhs, const catbot_interfaces__action__VlaTask_SendGoal_Request * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__copy(
  const catbot_interfaces__action__VlaTask_SendGoal_Request * input,
  catbot_interfaces__action__VlaTask_SendGoal_Request * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__init(catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__fini(catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence *
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__destroy(catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__are_equal(const catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * lhs, const catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence__copy(
  const catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * input,
  catbot_interfaces__action__VlaTask_SendGoal_Request__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_SendGoal_Response
 * )) before or use
 * catbot_interfaces__action__VlaTask_SendGoal_Response__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__init(catbot_interfaces__action__VlaTask_SendGoal_Response * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Response__fini(catbot_interfaces__action__VlaTask_SendGoal_Response * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_SendGoal_Response *
catbot_interfaces__action__VlaTask_SendGoal_Response__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Response__destroy(catbot_interfaces__action__VlaTask_SendGoal_Response * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__are_equal(const catbot_interfaces__action__VlaTask_SendGoal_Response * lhs, const catbot_interfaces__action__VlaTask_SendGoal_Response * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__copy(
  const catbot_interfaces__action__VlaTask_SendGoal_Response * input,
  catbot_interfaces__action__VlaTask_SendGoal_Response * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__init(catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__fini(catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence *
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__destroy(catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__are_equal(const catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * lhs, const catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence__copy(
  const catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * input,
  catbot_interfaces__action__VlaTask_SendGoal_Response__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_GetResult_Request
 * )) before or use
 * catbot_interfaces__action__VlaTask_GetResult_Request__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__init(catbot_interfaces__action__VlaTask_GetResult_Request * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Request__fini(catbot_interfaces__action__VlaTask_GetResult_Request * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_GetResult_Request *
catbot_interfaces__action__VlaTask_GetResult_Request__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Request__destroy(catbot_interfaces__action__VlaTask_GetResult_Request * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__are_equal(const catbot_interfaces__action__VlaTask_GetResult_Request * lhs, const catbot_interfaces__action__VlaTask_GetResult_Request * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__copy(
  const catbot_interfaces__action__VlaTask_GetResult_Request * input,
  catbot_interfaces__action__VlaTask_GetResult_Request * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__init(catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__fini(catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence *
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__destroy(catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__are_equal(const catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * lhs, const catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Request__Sequence__copy(
  const catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * input,
  catbot_interfaces__action__VlaTask_GetResult_Request__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_GetResult_Response
 * )) before or use
 * catbot_interfaces__action__VlaTask_GetResult_Response__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__init(catbot_interfaces__action__VlaTask_GetResult_Response * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Response__fini(catbot_interfaces__action__VlaTask_GetResult_Response * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_GetResult_Response *
catbot_interfaces__action__VlaTask_GetResult_Response__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Response__destroy(catbot_interfaces__action__VlaTask_GetResult_Response * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__are_equal(const catbot_interfaces__action__VlaTask_GetResult_Response * lhs, const catbot_interfaces__action__VlaTask_GetResult_Response * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__copy(
  const catbot_interfaces__action__VlaTask_GetResult_Response * input,
  catbot_interfaces__action__VlaTask_GetResult_Response * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__init(catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__fini(catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence *
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__destroy(catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__are_equal(const catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * lhs, const catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_GetResult_Response__Sequence__copy(
  const catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * input,
  catbot_interfaces__action__VlaTask_GetResult_Response__Sequence * output);

/// Initialize action/VlaTask message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * catbot_interfaces__action__VlaTask_FeedbackMessage
 * )) before or use
 * catbot_interfaces__action__VlaTask_FeedbackMessage__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__init(catbot_interfaces__action__VlaTask_FeedbackMessage * msg);

/// Finalize action/VlaTask message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_FeedbackMessage__fini(catbot_interfaces__action__VlaTask_FeedbackMessage * msg);

/// Create action/VlaTask message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_FeedbackMessage *
catbot_interfaces__action__VlaTask_FeedbackMessage__create();

/// Destroy action/VlaTask message.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_FeedbackMessage__destroy(catbot_interfaces__action__VlaTask_FeedbackMessage * msg);

/// Check for action/VlaTask message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__are_equal(const catbot_interfaces__action__VlaTask_FeedbackMessage * lhs, const catbot_interfaces__action__VlaTask_FeedbackMessage * rhs);

/// Copy a action/VlaTask message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__copy(
  const catbot_interfaces__action__VlaTask_FeedbackMessage * input,
  catbot_interfaces__action__VlaTask_FeedbackMessage * output);

/// Initialize array of action/VlaTask messages.
/**
 * It allocates the memory for the number of elements and calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__init(catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * array, size_t size);

/// Finalize array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__fini(catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * array);

/// Create array of action/VlaTask messages.
/**
 * It allocates the memory for the array and calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence *
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__create(size_t size);

/// Destroy array of action/VlaTask messages.
/**
 * It calls
 * catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
void
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__destroy(catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * array);

/// Check for action/VlaTask message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__are_equal(const catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * lhs, const catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * rhs);

/// Copy an array of action/VlaTask messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_catbot_interfaces
bool
catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence__copy(
  const catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * input,
  catbot_interfaces__action__VlaTask_FeedbackMessage__Sequence * output);

#ifdef __cplusplus
}
#endif

#endif  // CATBOT_INTERFACES__ACTION__DETAIL__VLA_TASK__FUNCTIONS_H_
