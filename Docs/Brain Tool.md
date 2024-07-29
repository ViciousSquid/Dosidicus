# Brain Tool
The **Brain Tool** allows for visualising and manipulating the Dosidicus neural network.

![image](https://github.com/user-attachments/assets/bde48677-587e-4751-9de6-f8a172b17f07)


### Network Tab

The Network is represented by interconnected `Neurons` with `weight values` between -1 and 1 

* Stronger weights are represented by thicker lines

The `Stimulate Brain` button allows for neurons to be manipulated to any value. It also allows setting of internal boolean `state indicators` such as "I am sleeping" , "I am pursuing food" and "I am sleeping"

Note that `satisfaction`, `anxiety`, `curiosity` cannot be modified - their values are affected by all the other neuron values.

See [https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Curiosity%2C%20Anxiety%2C%20Satisfaction.md]

The entire state of the brain can be saved out to a json file or a previously saved state can be loaded in.

### Data Tab

![image](https://github.com/user-attachments/assets/0c8ce9ab-9343-409a-94d0-748e5b0733ab)

This tab shows every neuron against every weight, including internal boolean `state indicators` (pastel colours)

Each column updates once per second. 


### Training Tab
![image](https://github.com/user-attachments/assets/bdab216c-8d39-48f6-aa48-030f97b77dc3)

This Tab implements basic tools for **Capturing** (recording) `training data` for Hebbian learning.

Select the 'capture learning data' checkbox to start capturing. The captured data will be displayed in real-time in the columns and a copy will be saved to `training-data` folder as a single file - the folder will be created if it does not exist.

Once sufficient data has bee captured, the network can be trained using the 'Train Hebbian' button - This will automatically open the console tab and show the progress.

For some more information on Hebbian learning, [see this article](https://medium.datadriveninvestor.com/what-is-hebbian-learning-3a027e8e4bbb)
