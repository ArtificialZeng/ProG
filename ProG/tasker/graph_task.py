import torch
import torchmetrics
from torch_geometric.loader import DataLoader
import torch.nn.functional as F
from .task import BaseTask
from ProG.utils import center_embedding
from ProG.utils import Gprompt_tuning_loss

class GraphTask(BaseTask):
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs)

    
    def train(self, train_loader):
        if self.prompt_type == 'None':
            return self.Train(train_loader)
        elif self.prompt_type == 'ProG':
            return self.ProGTrain(train_loader)
        elif self.prompt_type in ['gpf', 'gpf-plus']:
            return self.GPFTrain(train_loader)
        elif self.prompt_type =='Gprompt':
            return self.GpromptTrain(train_loader)
    
    def Train(self, train_loader):
        self.gnn.train()
        total_loss = 0.0 
        for batch in train_loader:  
            self.optimizer.zero_grad() 
            batch = batch.to(self.device)
            out = self.gnn(batch.x, batch.edge_index, batch.batch)
            out = self.answering(out)
            loss = self.criterion(out, batch.y)  
            loss.backward()  
            self.optimizer.step()  
            total_loss += loss.item()  
        return total_loss / len(train_loader)  
        
    def ProGTrain(self, train_loader):
        self.prompt.train()
        total_loss = 0.0 
        for batch in train_loader:
            self.optimizer.zero_grad()
            batch = batch.to(self.device)
            emb0 = self.gnn(batch.x, batch.edge_index, batch.batch)
            pg_batch = self.prompt.inner_structure_update()
            pg_batch = pg_batch.to(self.device)
            pg_emb = self.gnn(pg_batch.x, pg_batch.edge_index, pg_batch.batch)
            # cross link between prompt and input graphs
            dot = torch.mm(emb0, torch.transpose(pg_emb, 0, 1))
            sim = torch.softmax(dot, dim=1)
            loss = self.criterion(sim, batch.y)
            loss.backward()
            self.optimizer.step()
            total_loss += loss.item()  
        return total_loss / len(train_loader)  

    def GPFTrain(self, train_loader):
        self.gnn.train()
        total_loss = 0.0 
        for batch in train_loader:  
            self.optimizer.zero_grad() 
            batch = batch.to(self.device)
            batch.x = self.prompt.add(batch.x)
            out = self.gnn(batch.x, batch.edge_index, batch.batch, prompt = self.prompt, prompt_type = self.prompt_type)
            out = self.answering(out)
            loss = self.criterion(out, batch.y)  
            loss.backward()  
            self.optimizer.step()  
            total_loss += loss.item()  
        return total_loss / len(train_loader)  
    
    def GpromptTrain(self, train_loader):
        self.gnn.train()
        total_loss = 0.0 
        for batch in train_loader:  
            self.optimizer.zero_grad() 
            batch = batch.to(self.device)
            out = self.gnn(batch.x, batch.edge_index, batch.batch, prompt = self.prompt, prompt_type = self.prompt_type)
            # out = s𝑡,𝑥 = ReadOut({p𝑡 ⊙ h𝑣 : 𝑣 ∈ 𝑉 (𝑆𝑥)}),
            center = center_embedding(out, batch.y, self.output_dim)
            criterion = Gprompt_tuning_loss()
            loss = criterion(out, center, batch.y)  
            loss.backward()  
            self.optimizer.step()  
            total_loss += loss.item()  
        return total_loss / len(train_loader)  
        
    def GpromptTest(self, loader):
        self.gnn.eval()
        correct = 0
        for batch in loader: 
            batch = batch.to(self.device) 
            out = self.gnn(batch.x, batch.edge_index, batch.batch, prompt = self.prompt, prompt_type = self.prompt_type)
            pred = out.argmax(dim=1)  
            correct += int((pred == batch.y).sum())  
        acc = correct / len(loader.dataset)
        return acc  
    
    def test(self, loader):
        self.gnn.eval()
        correct = 0
        for batch in loader: 
            batch = batch.to(self.device) 
            if self.prompt_type in ['gpf', 'gpf-plus']:
                batch.x = self.prompt.add(batch.x)
            out = self.gnn(batch.x, batch.edge_index, batch.batch, prompt = self.prompt, prompt_type = self.prompt_type)
            out = self.answering(out)  
            pred = out.argmax(dim=1)  
            correct += int((pred == batch.y).sum())  
        acc = correct / len(loader.dataset)
        return acc  
    
    def acc_f1_over_batches(self, test_loader, num_class):
        accuracy = torchmetrics.classification.Accuracy(task="multiclass", num_classes=num_class).to(self.device)
        macro_f1 = torchmetrics.classification.F1Score(task="multiclass", num_classes=num_class, average="macro").to(self.device)
        accuracy.reset()
        macro_f1.reset()
        for batch_id, test_batch in enumerate(test_loader):
            test_batch = test_batch.to(self.device)
            emb0 = self.gnn(test_batch.x, test_batch.edge_index, test_batch.batch)
            pg_batch = self.prompt.token_view()
            pg_batch = pg_batch.to(self.device)
            pg_emb = self.gnn(pg_batch.x, pg_batch.edge_index, pg_batch.batch)
            dot = torch.mm(emb0, torch.transpose(pg_emb, 0, 1))
            pre = torch.softmax(dot, dim=1)

            y = test_batch.y
            pre_cla = torch.argmax(pre, dim=1)

            acc = accuracy(pre_cla, y)
            ma_f1 = macro_f1(pre_cla, y)

        acc = accuracy.compute()
        ma_f1 = macro_f1.compute()
        return acc
    
    def run(self):

        train_loader = DataLoader(self.train_dataset, batch_size=16, shuffle=True)
        test_loader = DataLoader(self.test_dataset, batch_size=16, shuffle=False)
        val_loader = DataLoader(self.val_dataset, batch_size=16, shuffle=False)
        print("prepare data is finished!")
        best_val_acc = final_test_acc = 0
        
        for epoch in range(1, self.epochs):
            loss = self.train(train_loader)
            if self.prompt_type == 'ProG':
                test_acc = self.acc_f1_over_batches(test_loader, self.output_dim)
                val_acc = self.acc_f1_over_batches(val_loader, self.output_dim)
            else:
                test_acc = self.test(test_loader)
                val_acc = self.test(val_loader)
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                final_test_acc = test_acc
            print("Epoch {:03d} | Loss {:.4f} | val Accuracy {:.4f} | test Accuracy {:.4f} ".format(epoch, loss, val_acc, test_acc))
        print(f'Final Test: {final_test_acc:.4f}')
        
        print("Graph Task completed")

        

        
