import torch
from ProG.model import GAT, GCN, GCov, GIN, GraphSAGE, GraphTransformer
from ProG.data import load4node, load4graph
from torch.optim import Adam

class PreTrain(torch.nn.Module):
    def __init__(self, gnn_type='TransformerConv', dataset_name = 'Cora', hid_dim = 128, gln = 2, num_epoch=100):
        super().__init__()
        self.device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
        self.dataset_name = dataset_name
        self.gnn_type = gnn_type
        self.num_layer = gln
        self.epochs = num_epoch
        self.hid_dim =hid_dim
       
        
    
    def initialize_gnn(self, input_dim, out_dim):
        if self.gnn_type == 'GAT':
                self.gnn = GAT(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        elif self.gnn_type == 'GCN':
                self.gnn = GCN(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        elif self.gnn_type == 'GraphSAGE':
                self.gnn = GraphSAGE(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        elif self.gnn_type == 'GIN':
                self.gnn = GIN(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        elif self.gnn_type == 'GCov':
                self.gnn = GCov(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        elif self.gnn_type == 'GraphTransformer':
                self.gnn = GraphTransformer(input_dim = input_dim, out_dim = out_dim, num_layer = self.num_layer)
        else:
                raise ValueError(f"Unsupported GNN type: {self.gnn_type}")
        self.gnn.to(self.device)
        self.optimizer = Adam(self.gnn.parameters(), lr=0.001, weight_decay=0.00005)

    def load_graph_data(self):
        self.input_dim, self.output_dim, _, _, _, self.graph_list= load4graph(self.dataset_name)
        
#     def load_node_data(self):
#         self.data, self.dataset = load4node(self.dataset_name, shot_num = self.shot_num)
#         self.data.to(self.device)
#         self.input_dim = self.dataset.num_features
#         self.output_dim = self.dataset.num_classes

