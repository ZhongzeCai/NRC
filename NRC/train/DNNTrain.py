from NRC.losses import mse_loss, rmse_loss, mean_std_norm_loss
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from torch.utils.data import TensorDataset, DataLoader


            
def DNN_Trainer(
            model,
            X_train, Y_train, X_val, Y_val,
            bat_size = 128,
            LR = 1E-2,
            Decay = 1E-4,
            N_Epoch = 300,
            validate_times = 20,
            verbose = True,
            train_loss = mean_std_norm_loss,
            val_loss_criterias = {
                "nll" : mean_std_norm_loss,
                "rmse": rmse_loss
            },
            early_stopping = True,
            patience = 10,
            monitor_name = "nll",
            backdoor = None,
            harvestor = None,
            **kwargs
        ):
    
    optimizer = optim.Adam(model.parameters(), lr = LR, weight_decay=Decay)


    if not harvestor:

        harvestor = {
            "training_losses": []
        }
        if early_stopping:
            harvestor["early_stopped"] = False
            harvestor["early_stopping_epoch"] = 0
            harvestor["monitor_name"] = monitor_name
            harvestor["monitor_vals"] = []

        for key in val_loss_criterias.keys():
            harvestor["val_"+key] = []

    else:

        # we are assuming that a harvestor is carefully written and carefully inserted

        assert len(harvestor["training_losses"]) == 0

        if early_stopping:

            assert "early_stopped" in harvestor.keys() and not harvestor["early_stopped"]
            assert harvestor["early_stopping_epoch"] == 0
            assert len(harvestor["monitor_vals"]) == 0

        for key in val_loss_criterias.keys():
            assert len(harvestor["val_"+key]) == 0


        


    if isinstance(X_train, np.ndarray):

        X_train, Y_train, X_val, Y_val = map(torch.Tensor, [X_train, Y_train, X_val, Y_val])
    

    training_set = TensorDataset(X_train, Y_train)

    if backdoor and backdoor == "MMD_LocalTrain":
        training_loader = DataLoader(training_set, batch_size=bat_size, shuffle=False)
    else:
        training_loader = DataLoader(training_set, batch_size=bat_size, shuffle=True)

    PREV_loss = 1E5

    if early_stopping:
        patience_count = 0

    for epoch in range(N_Epoch):
        for i_bat, (X_bat, Y_bat) in enumerate(training_loader):

            optimizer.zero_grad()

            loss = train_loss(model.forward(X_bat), Y_bat)

            loss.backward()

            optimizer.step()


        # we always want to validate
        harvestor["training_losses"].append(loss.item())

        val_output = model.predict(X_val)

        if early_stopping:
            patience_val_loss = val_loss_criterias[monitor_name](val_output, Y_val).item()

            harvestor["monitor_vals"].append(patience_val_loss)

            if patience_val_loss > PREV_loss:
                patience_count += 1
            
            PREV_loss = patience_val_loss


        

        
        if early_stopping and patience_count >= patience:

            if verbose:

                print("Early Stopped at Epoch ", epoch)
            
            harvestor["early_stopped"] = True
            harvestor["early_stopping_epoch"] = epoch


            break

        if epoch % int(N_Epoch / validate_times) == 0:

            
            if verbose:
                print("epoch ", epoch)
            for name in val_loss_criterias.keys():

                val_loss = val_loss_criterias[name](val_output, Y_val).item()

                harvestor["val_"+name].append(val_loss)

                if verbose:
                    print("     loss: {0}, {1}".format(name, val_loss))

