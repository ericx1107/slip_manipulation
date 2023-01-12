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
#from slip_manipulation import UR5Moveit

class UR5Moveit():
    
    def __init__(self):
        
        sleep(0.1) # Allow controller to start up (called in bash script)
        rospy.init_node('aruco_test')

        # initialise moveit planning scene
        self.scene = moveit_commander.PlanningSceneInterface(synchronous=True)
        self.table_size = [2, 2, 0.87]

        self.arm = moveit_commander.MoveGroupCommander('manipulator')
        self.arm.set_planner_id("PRM") # /home/acrv/HRIGroupAdmin/example_ros_ws/src/universal_robot/ur5_moveit_config/config/ompl_planning.yaml

        self.init_planning_scene()

        # initialise joint constraints to prevent collision with camera mount
        self.init_moveit_constraints()

        # define important poses
        # self.arm.set_named_target("up") # go to up position if not already there
        self.start_pose = {
            'shoulder_pan_joint': 0,
            'shoulder_lift_joint': -np.pi/2,
            'elbow_joint': -np.pi/2,
            'wrist_1_joint': -np.pi/2,
            'wrist_2_joint': np.pi/2,
            'wrist_3_joint': np.pi
        }

        # move to start pose
        # self.move_to_joints_pose(self.start_pose)

    def init_planning_scene(self):
        # add table collision object
        box_pose = PoseStamped()
        box_pose.header.frame_id = "base_link"
        box_pose.pose.position.x = 0
        box_pose.pose.position.y = 0
        box_pose.pose.position.z = box_pose.pose.position.z - .44 # shift by table size/2
        box_name = "table"
        self.scene.add_box(box_name, box_pose, size=self.table_size)

    def init_moveit_constraints(self):
        self.camera_constraints = Constraints()
        self.camera_constraints.name = 'camera'
        
        joint_constraint = JointConstraint()
        joint_constraint.joint_name = 'wrist_2_joint'
        joint_constraint.position = 0
        joint_constraint.tolerance_above = 2.55
        joint_constraint.tolerance_below = 2.55
        joint_constraint.weight = 1
        
        self.camera_constraints.joint_constraints.append(joint_constraint)

        self.arm.set_path_constraints(self.camera_constraints)
        

    def move_to_joints_pose(self, goal_pose):
        self.arm.set_joint_value_target(goal_pose)

        plan = self.arm.plan()

        raw_input('Check Rviz for plan, press enter to execute')

        self.arm.execute(plan)

ur5 = UR5Moveit()

ur5.arm.set_pose_reference_frame('base_link')
ee_link = ur5.arm.get_end_effector_link()
start_pose = ur5.arm.get_current_pose(ee_link).pose
print(start_pose)
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
ur5.arm.execute(plan)