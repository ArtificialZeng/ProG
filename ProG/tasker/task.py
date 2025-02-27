import torch
from ProG.model import GAT, GCN, GCov, GIN, GraphSAGE, GraphTransformer, GPPT
from ProG.prompt import GPF, GPF_plus, LightPrompt, Gprompt, GPPTPrompt
from torch import nn, optim
from ProG.data import load4node, load4graph
from ProG.utils import Gprompt_tuning_loss
import numpy as np

class BaseTask:
    def __init__(self, pre_train_model_path=None, gnn_type='TransformerConv', hid_dim = 128, num_layer = 2, dataset_name='Cora', prompt_type='gpf', epochs=100, shot_num=10):
        self.pre_train_model_path = pre_train_model_path
        self.device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
        self.hid_dim = hid_dim
        self.num_layer = num_layer
        self.dataset_name = dataset_name
        self.shot_num = shot_num
        self.gnn_type = gnn_type
        self.prompt_type = prompt_type
        self.epochs = epochs
        if dataset_name in ['PubMed', 'CiteSeer', 'Cora']:
            self.load_node_data()
        if dataset_name in ['MUTAG', 'ENZYMES', 'COLLAB', 'PROTEINS', 'IMDB-BINARY', 'REDDIT-BINARY']:
            self.load_graph_data()
        self.initialize_gnn()
        self.initialize_prompt()
        self.answering =  torch.nn.Sequential(torch.nn.Linear(self.hid_dim, self.output_dim),
                                            torch.nn.Softmax(dim=1)).to(self.device)
        self.initialize_optimizer()
        self.initialize_loss()

    def initialize_optimizer(self):
        if self.prompt_type == 'None':
            model_param_group = []
            model_param_group.append({"params": self.gnn.parameters()})
            model_param_group.append({"params": self.answering.parameters()})
            self.optimizer = optim.Adam(model_param_group, lr=0.005, weight_decay=5e-4)
        elif self.prompt_type == 'ProG':
            self.optimizer = optim.Adam(filter(lambda p: p.requires_grad, self.prompt.parameters()), lr=0.001, weight_decay= 0.00001)
        elif self.prompt_type in ['gpf', 'gpf-plus']:
            model_param_group = []
            model_param_group.append({"params": self.prompt.parameters()})
            model_param_group.append({"params": self.answering.parameters()})
            self.optimizer = optim.Adam(model_param_group, lr=0.005, weight_decay=5e-4)
        elif self.prompt_type in ['Gprompt', 'gppt']:
            self.optimizer = optim.Adam(self.prompt.parameters(), lr=0.005, weight_decay=5e-4)


    def initialize_loss(self):
        self.criterion = torch.nn.CrossEntropyLoss()
        if self.prompt_type == 'Gprompt':
            self.criterion = Gprompt_tuning_loss()
            
    def initialize_prompt(self):
        if self.prompt_type == 'None':
            self.prompt = None
        elif self.prompt_type == 'gppt':
            self.prompt = GPPTPrompt(self.hid_dim, self.output_dim, self.output_dim, device = self.device)
            train_ids = torch.nonzero(self.data.train_mask, as_tuple=False).squeeze()
            node_embedding = self.gnn(self.data.x, self.data.edge_index)
            self.prompt.weigth_init(node_embedding,self.data.edge_index, self.data.y, train_ids)
        elif self.prompt_type =='ProG':
            lr, wd = 0.001, 0.00001
            self.prompt = LightPrompt(token_dim=self.input_dim, token_num_per_group=100, group_num=self.output_dim, inner_prune=0.01)
            for p in self.gnn.parameters():
                p.requires_grad = False
            self.optimizer  = optim.Adam(filter(lambda p: p.requires_grad, self.prompt.parameters()),lr=lr, weight_decay=wd)
        elif self.prompt_type == 'gpf':
            self.prompt = GPF(self.input_dim).to(self.device)
        elif self.prompt_type == 'gpf-plus':
            self.prompt = GPF_plus(self.input_dim, 20).to(self.device)
        elif self.prompt_type == 'Gprompt':
            self.prompt = Gprompt(self.hid_dim).to(self.device)
        else:
            raise KeyError(" We don't support this kind of prompt.")

    def initialize_gnn(self):
        if self.gnn_type == 'GAT':
                self.gnn = GAT(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        elif self.gnn_type == 'GCN':
                self.gnn = GCN(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        elif self.gnn_type == 'GraphSAGE':
                self.gnn = GraphSAGE(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        elif self.gnn_type == 'GIN':
                self.gnn = GIN(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        elif self.gnn_type == 'GCov':
                self.gnn = GCov(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        elif self.gnn_type == 'GraphTransformer':
                self.gnn = GraphTransformer(input_dim=self.input_dim, out_dim=self.hid_dim, num_layer=self.num_layer)
        else:
                raise ValueError(f"Unsupported GNN type: {self.gnn_type}")
        self.gnn.to(self.device)

        if self.pre_train_model_path != 'None':
            if self.gnn_type not in self.pre_train_model_path:
                raise ValueError(f"the Downstream gnn '{self.gnn_type}' does not match the pre-train model")
            if self.dataset_name not in self.pre_train_model_path:
                raise ValueError(f"the Downstream dataset '{self.dataset_name}' does not match the pre-train dataset")

            self.gnn.load_state_dict(torch.load(self.pre_train_model_path, map_location=self.device))
            print("Successfully loaded pre-trained weights!")

    def load_graph_data(self):
            self.input_dim, self.output_dim, self.train_dataset, self.test_dataset, self.val_dataset, _= load4graph(self.dataset_name, self.shot_num)
        
    def load_node_data(self):
            self.data, self.dataset = load4node(self.dataset_name, shot_num = self.shot_num)
            self.data.to(self.device)
            self.input_dim = self.dataset.num_features
            self.output_dim = self.dataset.num_classes
      
