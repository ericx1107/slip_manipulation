#! /usr/bin/env python

import rospy
import tf2_ros
import tf
import numpy as np
from geometry_msgs.msg import Pose, Point, Quaternion
from slip_manipulation.get_tf_helper import *
from slip_manipulation.msg import AngleStamped

class StateEstimator():
    def __init__(self, box_dim):
        self.box_dim = box_dim # lwh
        self.box_length = box_dim[0]
        self.box_width = box_dim[1]
        self.box_height = box_dim[2]
        
        # ros publishers and subscribers
        self.angle_pub = rospy.Publisher('/slip_manipulation/rotation_angle', AngleStamped, queue_size=1)
        self.lowest_vertex_pub = rospy.Publisher('/slip_manipulation/lowest_vertex', Point, queue_size=1)

        # tf things
        self.listener = tf.TransformListener()
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)

        # initialise
        self.upright_axis = self.get_upright_axis()
        
    def vision_estimate_contact_config(self, contact=True):

        trans = patient_lookup_box_tf(self.tf_buffer, loop=True)

        # get rotation matrix from euler angles
        orientation_rpy = np.array(tf.transformations.euler_from_quaternion([trans.transform.rotation.x, 
                                                                                        trans.transform.rotation.y, 
                                                                                        trans.transform.rotation.z, 
                                                                                        trans.transform.rotation.w]))

        # describes the axis orientations in terms of the base_link axes
        box_rot_mat = tf.transformations.euler_matrix(*orientation_rpy, axes='sxyz')[:3, :3]

        base_z_axis = [0, 0, 1]

        # find the box axis that is roughly pointing up (smallest angle between this and base_link z axis)
        angles = []

        for col in range(box_rot_mat.shape[1]):
            box_axis = box_rot_mat[:, col]
            angle = np.arccos(np.dot(box_axis, base_z_axis) / (np.linalg.norm(box_axis) * np.linalg.norm(base_z_axis)))
            angles.append(angle)

        # check for close to 0
        min_angle_idx = np.argmin(angles)
        min_angle_deg = angles[min_angle_idx] * 180/np.pi
        # check for close to 180
        max_angle_idx = np.argmax(angles)
        max_angle_deg = angles[max_angle_idx] * 180/np.pi
        
        if contact is None:
            return
        elif not contact:
            print("No contact")

        tol = 3 # degrees tolerance
        if np.isclose(min_angle_deg, 0, atol=tol) or np.isclose(min_angle_deg, -180, atol=tol) or np.isclose(max_angle_deg, 180, atol=tol):
            print("Contact through SURFACE")
        else:
            print("Contact through EDGE")

    def vision_estimate_contact(self):
        # check all eight vertices of the box
        coords = []
        coords.append((self.box_dim[0]/2, self.box_dim[1]/2, self.box_dim[2]/2))
        coords.append((self.box_dim[0]/2, self.box_dim[1]/2, -self.box_dim[2]/2))
        coords.append((self.box_dim[0]/2, -self.box_dim[1]/2, self.box_dim[2]/2))
        coords.append((self.box_dim[0]/2, -self.box_dim[1]/2, -self.box_dim[2]/2))
        coords.append((-self.box_dim[0]/2, self.box_dim[1]/2, self.box_dim[2]/2))
        coords.append((-self.box_dim[0]/2, self.box_dim[1]/2, -self.box_dim[2]/2))
        coords.append((-self.box_dim[0]/2, -self.box_dim[1]/2, self.box_dim[2]/2))
        coords.append((-self.box_dim[0]/2, -self.box_dim[1]/2, -self.box_dim[2]/2))

        z_height = []
        for coord in coords:
            vertex = Pose(Point(*coord), Quaternion(0, 0, 0, 1))
            base_vertex = tf_transform_pose(self.listener, vertex, 'box_origin', 'base_link', loop=False)
            if base_vertex is None:
                return
            z_height.append(base_vertex.pose.position.z)
        
        min_z_idx = np.argmin(z_height)
        min_z = z_height[min_z_idx]

        second_min_z = np.partition(z_height, 1)[1]

        if min_z > 0.02:
            print("No contact")
            return False

        elif min_z < 0.02 and not np.isclose(min_z, second_min_z, atol=0.01):
            print("Contact through VERTEX")
            return None

        else:
            return True

    def vision_estimate_lowest_vertex(self):
        # init all eight vertices of the box
        coords = []
        coords.append((self.box_dim[0]/2, self.box_dim[2]/2, self.box_dim[1]/2))
        coords.append((self.box_dim[0]/2, self.box_dim[2]/2, -self.box_dim[1]/2))
        coords.append((self.box_dim[0]/2, -self.box_dim[2]/2, self.box_dim[1]/2))
        coords.append((self.box_dim[0]/2, -self.box_dim[2]/2, -self.box_dim[1]/2))
        coords.append((-self.box_dim[0]/2, self.box_dim[2]/2, self.box_dim[1]/2))
        coords.append((-self.box_dim[0]/2, self.box_dim[2]/2, -self.box_dim[1]/2))
        coords.append((-self.box_dim[0]/2, -self.box_dim[2]/2, self.box_dim[1]/2))
        coords.append((-self.box_dim[0]/2, -self.box_dim[2]/2, -self.box_dim[1]/2))

        z_height = []
        vertices = []
        for coord in coords:
            # convert to base_link frame to get height from base
            vertex = Pose(Point(*coord), Quaternion(0, 0, 0, 1))
            base_vertex = tf_transform_pose(self.listener, vertex, 'box_origin', 'base_link', loop=False)
            if base_vertex is None:
                rospy.logerr('No box transform')
                return
            # save height in z dimension
            z_height.append(base_vertex.pose.position.z)
            vertices.append(base_vertex)
        
        # find min
        min_z_idx = np.argmin(z_height)
        # print(z_height[min_z_idx])
        lowest_vertex = vertices[min_z_idx].pose.position
        
        # publish vertex as Point msg
        self.lowest_vertex_pub.publish(lowest_vertex)

    def get_upright_axis(self):
        # check upright edge using transform from base_link
        trans = patient_lookup_box_tf(self.tf_buffer, loop=True)

        # get rotation matrix for condition check
        orientation_rpy = np.array(tf.transformations.euler_from_quaternion([trans.transform.rotation.x, 
                                                                                        trans.transform.rotation.y, 
                                                                                        trans.transform.rotation.z, 
                                                                                        trans.transform.rotation.w]))
        # orientation_rpy_for_print = orientation_rpy * 180/np.pi
        # print(orientation_rpy_for_print)
        
        tol = 0.2 # absolute tolerance, for value that should be between -1 to 1

        rot_mat = tf.transformations.euler_matrix(*orientation_rpy, axes='sxyz')[:3, :3]
        # print(rot_mat)
        new_z = rot_mat[:, 2]

        # need to find axis that is pointing in the direction of the z axis of the base_link frame (upright)
        # for rotation matrix: find column with [0; 0; 1] (roughly)
        # that column represents the axis that is transformed to point in the direction of the original z axis
        # if -1 that means it's pointing in opposite directino to original z (down)

        if all(np.isclose(new_z, [0, 0, 1], atol=tol)) or all(np.isclose(new_z, [0, 0, -1], atol=tol)):
            # print("z axis (blue) is vertical, long side")
            z_ori_coeff = np.sign(rot_mat[2, 2])    # is the new axis pointing in the same direction as the old z axis (up)?
                                                    # 1 if same direction, -1 if opposite
            return new_z
            return (np.array([0, 0, 1]) * z_ori_coeff, 2)

        elif all(np.isclose(new_z, [1, 0, 0], atol=tol)) or all(np.isclose(new_z, [-1, 0, 0], atol=tol)):
            # print("x axis (red) is vertical, short side")
            z_ori_coeff = np.sign(rot_mat[0, 2])    # is the new axis pointing in the same direction as the old z axis (up)?
                                                    # 1 if same direction, -1 if opposite
            return new_z
            return (np.array([1, 0, 0]) * z_ori_coeff, 0)

        elif all(np.isclose(new_z, [0, 1, 0], atol=tol)) or all(np.isclose(new_z, [0, -1, 0], atol=tol)):
            print("y axis (green) is vertical, no graspable edge!")
            # v_offset = self.box_dim[2]/2
            return 
        else:
            print("Uncaught case for object position. No side facing up found.")
            return

    def vision_estimate_rotation_angle(self):
        try:
            trans = self.tf_buffer.lookup_transform('box_origin', 'base_link', rospy.Time(0), timeout=rospy.Duration(2))
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            print("Waiting for box transform\n")
            return

        # get rotation matrix from euler angles
        orientation_rpy = np.array(tf.transformations.euler_from_quaternion([trans.transform.rotation.x, 
                                                                                        trans.transform.rotation.y, 
                                                                                        trans.transform.rotation.z, 
                                                                                        trans.transform.rotation.w]))

        # describes the axis orientations in terms of the base_link axes
        box_rot_mat = tf.transformations.euler_matrix(*orientation_rpy, axes='sxyz')[:3, :3]

        box_axis = box_rot_mat[:, 2]
        angle = np.arccos(np.dot(box_axis, self.upright_axis) / (np.linalg.norm(box_axis) * np.linalg.norm(self.upright_axis)))
        angle *= 180/np.pi

        angle_stamped = AngleStamped()
        angle_stamped.header.stamp = rospy.Time.now()
        angle_stamped.header.frame_id = "base_link"
        
        angle_stamped.angle = angle

        self.angle_pub.publish(angle_stamped)

if __name__ == "__main__":
    pass