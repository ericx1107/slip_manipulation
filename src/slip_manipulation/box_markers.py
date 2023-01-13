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
    def __init__(self):
        # ros publishers and subscribers
        self.markers_sub = rospy.Subscriber('/aruco_marker_publisher/markers', 
            MarkerArray, self.marker_callback)

        self.markers_pose_pub = rospy.Publisher('/slip_manipulation/marker_pose', PoseStamped, queue_size=1)
        
        self.visualise_box_pub = rospy.Publisher('/slip_manipulation/box_visualisation', Marker, queue_size=1)
        
        self.centre_grasp_pub = rospy.Publisher('/slip_manipulation/centre_grasp', PoseStamped, queue_size=1)
        self.pos_grasp_pub = rospy.Publisher('/slip_manipulation/pos_grasp', PoseStamped, queue_size=1)
        self.neg_grasp_pub = rospy.Publisher('/slip_manipulation/neg_grasp', PoseStamped, queue_size=1)

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
            
            self.generate_grasp_pose()
        
        self.shutdown_detector() # only detect once

    def publish_marker_transform(self, pose_stamped, marker_id):
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
        if marker_id == 3:
            z_offset = -self.box_dim[1]/2
            rot_rpy = (0, 0, 0)             # TODO: match all axes of box_origin frame after converting
        elif marker_id == 4:
            z_offset = -self.box_dim[1]/2
            rot_rpy = (0, 0, np.pi/2)
        elif marker_id == 5 or marker_id == 6:
            z_offset = -self.box_dim[0]/2
            rot_rpy = (0, np.pi/2, np.pi/2)
        elif marker_id == 1:
            z_offset = -self.box_dim[2]/2
            rot_rpy = (np.pi/2, 0, np.pi/2)
        elif marker_id == 2:
            z_offset = -self.box_dim[2]/2
            rot_rpy = (np.pi/2, 0, 0)
            
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
            print("Can't see box!\n")
            return
        
        mkr = Marker()
        mkr.header = box_from_base_stamped.header
        mkr.ns = "box"
        mkr.id = 0
        mkr.type = Marker.CUBE
        mkr.action = Marker.ADD
        mkr.pose = box_from_base_stamped.pose
        mkr.scale.x = 0.18
        mkr.scale.y = 0.04
        mkr.scale.z = 0.114
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
    
    def generate_grasp_pose(self):
        # assuming that at the beginning the box is upright
        finger_offset = 0.02
        
        # check upright edge using transform from base_link
        trans = self.tf_buffer.lookup_transform('box_origin', 'base_link', rospy.Time(0), timeout=rospy.Duration(2))
        orientation_rpy = np.array(tf_conversions.transformations.euler_from_quaternion([trans.transform.rotation.x, 
                                                                                        trans.transform.rotation.y, 
                                                                                        trans.transform.rotation.z, 
                                                                                        trans.transform.rotation.w]))
        orientation_rpy = orientation_rpy * 180/np.pi
        # print(orientation_rpy)
        
        tol = 10 # angle tolerance
        
        edge_centre_pose = Pose()     # initialise zero pose for side
        edge_centre_pose.position.x = 0
        edge_centre_pose.position.y = 0
        edge_centre_pose.position.z = 0
        edge_centre_pose.orientation.x = 0
        edge_centre_pose.orientation.y = 0
        edge_centre_pose.orientation.z = 0
        edge_centre_pose.orientation.w = 1
        
        edge_neg_side_pose = copy.deepcopy(edge_centre_pose)
        edge_pos_side_pose = copy.deepcopy(edge_centre_pose)
        
        if any(np.isclose(orientation_rpy[0], [0, 180, -180], rtol=tol)) and any(np.isclose(orientation_rpy[1], [0, 180, -180], rtol=tol)):
            # print("z axis (blue) is vertical")
            v_offset = self.box_dim[1]/2
            h_offset = self.box_dim[0]/2
            
            edge_pos_side_pose.position.x += h_offset - finger_offset
            edge_neg_side_pose.position.x -= h_offset - finger_offset
            
            grasp_ori_rpy = [180, 0, 90]
        elif any(np.isclose(orientation_rpy[1], [90, -90], rtol=tol)) and any(np.isclose(orientation_rpy[2], [0, 180, -180], rtol=tol)):
            # print("x axis (red) is vertical")
            v_offset = self.box_dim[0]/2
            h_offset = self.box_dim[1]/2
            
            edge_pos_side_pose.position.z += h_offset - finger_offset
            edge_neg_side_pose.position.z -= h_offset - finger_offset
            
            grasp_ori_rpy = [0, 90, 180]
        elif any(np.isclose(orientation_rpy[0], [90, -90], rtol=tol)) and any(np.isclose(orientation_rpy[2], [0, 180, -180])):
            print("y axis (green) is vertical, no graspable edge!")
            # v_offset = self.box_dim[2]/2
            return
        
        # correct orientation of grasp pose
        grasp_ori_rpy = np.array(grasp_ori_rpy) * np.pi/180
        grasp_ori = Quaternion(*tf_conversions.transformations.quaternion_from_euler(*grasp_ori_rpy))
        
        edge_centre_pose.orientation = grasp_ori
        edge_pos_side_pose.orientation = grasp_ori
        edge_neg_side_pose.orientation = grasp_ori
        
        # apply h_offset then transform for h_offset to save splitting the unholy logic statements above
        try:
            edge_centre_pose = tf_transform_pose(self.tf_buffer, edge_centre_pose, 'box_origin', 'base_link')
            edge_pos_side_pose = tf_transform_pose(self.tf_buffer, edge_pos_side_pose, 'box_origin', 'base_link')
            edge_neg_side_pose = tf_transform_pose(self.tf_buffer, edge_neg_side_pose, 'box_origin', 'base_link')
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            print("Can't see box!\n")
            return
        
        # apply v_offset at the end
        # only works if assuming edge is facing up!
        edge_centre_pose.pose.position.z += v_offset
        edge_pos_side_pose.pose.position.z += v_offset
        edge_neg_side_pose.pose.position.z += v_offset
        
        # return or publish poses
        self.centre_grasp_pub.publish(edge_centre_pose)
        self.pos_grasp_pub.publish(edge_pos_side_pose)
        self.neg_grasp_pub.publish(edge_neg_side_pose)
        
    def shutdown_detector(self):
        self.markers_sub.unregister()
        
if __name__ == "__main__":
    pass