#! /usr/bin/env python

import rospy
import tf2_ros
import tf_conversions
import numpy as np
import copy
from aruco_msgs.msg import MarkerArray
from collections import defaultdict
from geometry_msgs.msg import Pose, PoseStamped, TransformStamped, Quaternion
from visualization_msgs.msg import Marker
from std_msgs.msg import Header
from slip_manipulation.get_tf_helper import *

class BoxMarkers():
    def __init__(self, box_dim, grasp_param=1, detect_once=False):
        self.box_dim = box_dim # lhw
        self.box_length = box_dim[0]
        self.box_height = box_dim[1]
        self.detect_once = detect_once
        self.grasp_param = grasp_param
        
        # ros publishers and subscribers
        self.markers_sub = rospy.Subscriber('/aruco_marker_publisher/markers', 
            MarkerArray, self.marker_callback)

        self.markers_pose_pub = rospy.Publisher('/slip_manipulation/marker_pose', PoseStamped, queue_size=1)
        
        self.visualise_box_pub = rospy.Publisher('/slip_manipulation/box_visualisation', Marker, queue_size=1)
        
        self.grasp_pub = rospy.Publisher('/slip_manipulation/grasp_pose', PoseStamped, queue_size=1)

        # self.marker_list = defaultdict(lambda: {"pose": 0})

        # tf things
        self.tf_broadcaster = tf2_ros.TransformBroadcaster()
        
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        
        # parameters
        self.box_pose = Pose()
    
    def marker_callback(self, marker_array):
        for marker in marker_array.markers:
            # self.marker_list[str(marker.id)]["pose"] = marker.pose.pose
            
            # construct stamped message
            stamped = PoseStamped()
            stamped.header = marker.header
            stamped.pose = marker.pose.pose

            self.box_dim = [0.18, 0.114, 0.04] # lwh

            # publish marker pose
            self.markers_pose_pub.publish(stamped)

            # publish tf's
            self.publish_marker_transform(stamped, marker.id)
            self.publish_box_origin_transform(marker.id)
        
            self.publish_box()
            
            self.generate_grasp_pose(self.grasp_param)
        
        if self.detect_once:
            self.shutdown_detector() # only detect once

    def publish_marker_transform(self, pose_stamped, marker_id):
        '''
        For visualisation in Rviz
        '''
        t = TransformStamped()

        t.header = pose_stamped.header
        t.header.stamp = rospy.Time.now()
        t.child_frame_id = 'marker_' + str(marker_id)
        t.transform.translation.x = pose_stamped.pose.position.x
        t.transform.translation.y = pose_stamped.pose.position.y
        t.transform.translation.z = pose_stamped.pose.position.z
        t.transform.rotation.x = pose_stamped.pose.orientation.x
        t.transform.rotation.y = pose_stamped.pose.orientation.y
        t.transform.rotation.z = pose_stamped.pose.orientation.z
        t.transform.rotation.w = pose_stamped.pose.orientation.w

        self.tf_broadcaster.sendTransform(t)

    def publish_box_origin_transform(self, marker_id):
        '''
        From marker position, publish the tf frame of the centre of the box
        '''
        if marker_id == 3:
            z_offset = -self.box_dim[1]/2
            rot_rpy = (0, 0, 0)
        elif marker_id == 4:
            z_offset = -self.box_dim[1]/2
            rot_rpy = (0, np.pi, np.pi/2)
        elif marker_id == 5:
            z_offset = -self.box_dim[0]/2
            rot_rpy = (0, -np.pi/2, np.pi/2)
        elif marker_id == 6:
            z_offset = -self.box_dim[0]/2
            rot_rpy = (np.pi, np.pi/2, np.pi/2)
        elif marker_id == 1:
            z_offset = -self.box_dim[2]/2
            rot_rpy = (-np.pi/2, np.pi, np.pi/2)
        elif marker_id == 2:
            z_offset = -self.box_dim[2]/2
            rot_rpy = (-np.pi/2, 0, np.pi)
        else:
            print("No valid marker detected")
            return

        # for other box
        # if marker_id == 3 or marker_id == 4:
        #     z_offset = -0.114/2
        # elif marker_id == 5 or marker_id == 6:
        #     z_offset = -0.18/2
        # elif marker_id == 1 or marker_id == 2:
        #     z_offset = -0.04/2    

        t = TransformStamped()

        t.header.stamp = rospy.Time.now()
        t.header.frame_id = 'marker_' + str(marker_id)
        t.child_frame_id = 'box_origin'
        t.transform.translation.x = 0
        t.transform.translation.y = 0
        t.transform.translation.z = z_offset
        q = tf_conversions.transformations.quaternion_from_euler(*rot_rpy)
        t.transform.rotation.x = q[0]
        t.transform.rotation.y = q[1]
        t.transform.rotation.z = q[2]
        t.transform.rotation.w = q[3]

        self.tf_broadcaster.sendTransform(t)

    def publish_box(self):
        '''
        Publish visualisation marker for visualisation in Rviz
        '''
        # construct Pose at the origin of box_origin frame
        box_pose = Pose()
        box_pose.position.x = 0
        box_pose.position.y = 0
        box_pose.position.z = 0
        box_pose.orientation.x = 0
        box_pose.orientation.y = 0
        box_pose.orientation.z = 0
        box_pose.orientation.w = 1
        
        # trans = self.tf_buffer.lookup_transform('box_origin', 'base_link', rospy.Time(0), timeout=rospy.Duration(2))
        # print("got transform")
        try:
            box_from_base_stamped = tf_transform_pose(self.tf_buffer, box_pose, 'box_origin', 'base_link')
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            print("Waiting for box transform\n")
            return
        
        mkr = Marker()
        mkr.header = box_from_base_stamped.header
        mkr.ns = "box"
        mkr.id = 0
        mkr.type = Marker.CUBE
        mkr.action = Marker.ADD
        mkr.pose = box_from_base_stamped.pose
        mkr.scale.x = self.box_dim[0]
        mkr.scale.y = self.box_dim[2]
        mkr.scale.z = self.box_dim[1]
        mkr.color.a = 1.0
        mkr.color.r = 0.0
        mkr.color.g = 0.0
        mkr.color.b = 1.0
    
        self.box_pose = box_from_base_stamped.pose
        # print(self.box_pose)
        # print_rpy = tf_conversions.transformations.euler_from_quaternion([self.box_pose.orientation.x, 
                                                                            # self.box_pose.orientation.y, 
                                                                            # self.box_pose.orientation.z, 
                                                                            # self.box_pose.orientation.w])
        # print('ori: ', np.array(print_rpy)*180/np.pi)
    
        self.visualise_box_pub.publish(mkr)
    
    def generate_grasp_pose(self, grasp_param=1):
        # check upright edge using transform from base_link
        try:
            trans = self.tf_buffer.lookup_transform('box_origin', 'base_link', rospy.Time(0), timeout=rospy.Duration(2))
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            print("Waiting for box transform\n")
            return
        
        # initialise zero pose to store info
        grasp_pose = Pose()
        grasp_pose.position.x = 0
        grasp_pose.position.y = 0
        grasp_pose.position.z = 0
        grasp_pose.orientation.x = 0
        grasp_pose.orientation.y = 0
        grasp_pose.orientation.z = 0
        grasp_pose.orientation.w = 1

        finger_offset = 0.02 # offset from side of box to grasp position

        # get rotation matrix for condition check
        orientation_rpy = np.array(tf_conversions.transformations.euler_from_quaternion([trans.transform.rotation.x, 
                                                                                        trans.transform.rotation.y, 
                                                                                        trans.transform.rotation.z, 
                                                                                        trans.transform.rotation.w]))
        # orientation_rpy_for_print = orientation_rpy * 180/np.pi
        # print(orientation_rpy_for_print)
        
        tol = 0.2 # absolute tolerance, for value that should be between -1 to 1

        rot_mat = tf_conversions.transformations.euler_matrix(*orientation_rpy, axes='sxyz')[:3, :3]
        # print(rot_mat)

        # need to find axis that is pointing in the direction of the z axis of the base_link frame (upright)
        # for rotation matrix: find column with [0; 0; 1] (roughly)
        # that column represents the axis that is transformed to point in the direction of the original z axis
        # if -1 that means it's pointing in opposite directino to original z (down)

        if all(np.isclose(rot_mat[:, 2], [0, 0, 1], atol=tol)) or all(np.isclose(rot_mat[:, 2], [0, 0, -1], atol=tol)):
            # print("z axis (blue) is vertical")
            v_offset = self.box_dim[1]/2
            h_offset = self.box_dim[0]/2
            
            # max grasp position given by dimension of box, with some space for the whole finger
            grasp_max = h_offset - finger_offset

            scaled_h_offset = grasp_max * grasp_param

            # apply horizontal offset using grasp parameter
            grasp_pose.position.x += scaled_h_offset
            # apply vertical offset
            grasp_pose.position.z += v_offset * np.sign(rot_mat[2, 2])
            
            grasp_ori_rpy = [180, 0, 90]
            
            if np.sign(rot_mat[2, 2]) == -1:
                grasp_ori_rpy = [0, 0, 90]
                
            # point y-axis of the gripper towards the origin of the box frame
            # find axis from box_origin that corresponds to this
            # can't be z axis since it is known to be vertical
            
            
        elif all(np.isclose(rot_mat[:, 2], [1, 0, 0], atol=tol)) or all(np.isclose(rot_mat[:, 2], [-1, 0, 0], atol=tol)):
            # print("x axis (red) is vertical")
            v_offset = self.box_dim[0]/2
            h_offset = self.box_dim[1]/2
            
            # max grasp position given by dimension of box, with some space for the whole finger
            grasp_max = h_offset - finger_offset

            scaled_h_offset = grasp_max * grasp_param

            # apply horizontal offset
            grasp_pose.position.z += scaled_h_offset
            # apply vertical offset
            grasp_pose.position.x += v_offset * np.sign(rot_mat[0, 2])
            
            grasp_ori_rpy = [0, 90, 180]
            
            if np.sign(rot_mat[0, 2]) == -1:
                grasp_ori_rpy = [0, 90, 0]

        elif all(np.isclose(rot_mat[:, 2], [0, 1, 0], atol=tol)) or all(np.isclose(rot_mat[:, 2], [0, -1, 0], atol=tol)):
            print("y axis (green) is vertical, no graspable edge!")
            # v_offset = self.box_dim[2]/2
            return
        else:
            print("Uncaught case for object position. No side facing up found.")
            return

        # correct orientation of grasp pose
        grasp_ori_rpy = np.array(grasp_ori_rpy) * np.pi/180
        grasp_ori = Quaternion(*tf_conversions.transformations.quaternion_from_euler(*grasp_ori_rpy))
        
        grasp_pose.orientation = grasp_ori
        
        # transform to base_link frame
        while True:
            try:
                grasp_pose = tf_transform_pose(self.tf_buffer, grasp_pose, 'box_origin', 'base_link')
                break
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                print("Waiting for box transform\n")
        
        # return or publish poses
        self.grasp_pub.publish(grasp_pose)
        
    def shutdown_detector(self):
        self.markers_sub.unregister()
        
if __name__ == "__main__":
    pass