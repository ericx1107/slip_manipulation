#! /usr/bin/env python

import rospy
import moveit_commander
import numpy as np
import open3d
from time import sleep
from std_msgs.msg import String
import roslib; roslib.load_manifest('robotiq_2f_gripper_control')
from robotiq_2f_gripper_control.msg import _Robotiq2FGripper_robot_output  as outputMsg
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import PointCloud2
from moveit_msgs.msg import Constraints, JointConstraint
from slip_manipulation.ur5_moveit import UR5Moveit
from slip_manipulation.box_markers import BoxMarkers

rospy.init_node('test_node')

ur5 = UR5Moveit()
# rospy.sleep(2)
# plan, _ = ur5.plan_cartesian_path(r = 0.09)
# raw_input("Enter to execute")
# ur5.arm.execute(plan)
box_dim = [0.18, 0.11, 0.04]
markers = BoxMarkers(box_dim, detect_once=False)

# while not rospy.is_shutdown():
#     markers.publish_box()
# rospy.sleep(2)
rospy.spin()

# ur5.arm.set_pose_reference_frame('base_link')

# input_pose = markers.marker_list["1"]["pose"]entation.y, 
                                                                            # self.box_pose.orientation.z, 
                                                                            # self.box_pose.orientation.w])
# print(type(input_pose))
# output_pose_stamped = ur5.tf_transform_pose(input_pose, 'camera_link', 'base_link')


# while not rospy.is_shutdown():
#     ur5.display_pose(output_pose_stamped)



'''ee_link = ur5.arm.get_end_effector_link()
start_pose = ur5.arm.get_current_pose(ee_link).pose
print(start_pose)
ur5 = UR5Moveit()
# goal_pose = [-0.150002384447, 0.0959219176177, 0.74666077793, 
# 0.658653290385, -0.611800540121, -0.269746822291, 0.345126924532]
# ur5.arm.set_pose_target(goal_pose)
start_pose.position.x += 0.1
goal_pose = [start_pose]
print(goal_pose)
plan, _ = ur5.arm.compute_cartesian_path(goal_pose, 0.01, 0.0)
# print(plan)
# plan = ur5.arm.plan()
raw_input('Press any button to execute')
ur5.arm.execute(plan)'''