import random

class node:
	def __init__(self, name, identifier, flags, bandwidth):
		self.name = name
		self.id = identifier
		self.flags = flags
		self.bandwidth = bandwidth

	def is_guard(self):
		return "Guard" in self.flags

	def is_valid(self):
		return "Valid" in self.flags

	def is_exit(self):
		return "Exit" in self.flags

	def is_bad_exit(self):
		return "BadExit" in self.flags

	def is_running(self):
		return "Running" in self.flags

	def is_fast(self):
		return "Fast" in self.flags

	def contains_flags(self, contains):
		for flag in contains:
			if flag not in self.flags:
				return False
		return True

	def is_adv(self):
		return "Adv" in self.flags

class consensus:
	def __init__(self, consensus_file):
		self.consensus_file = consensus_file
		self.nodes = []
		self.weights = {}
		self.bwweight_scale = 10000 # default value if not provided by consensus file

	def parse_consensus(self):
		with open(self.consensus_file, "r") as cf:
			# read lines and create nodes
			name = None
			identifier = None
			flags = None
			bandwidth = None

			first_node = True

			line = cf.readline()
			while line:
				tokens = line.split() # tokenize the line on spaces
				prefix = tokens[0]
				if prefix == "r": # came to new node
					if not first_node:
						if name == None or flags == None or bandwidth == None or identifier == None: # if we didnt fill any of the parameters
							print("ERROR")
							print("name = ", name)
							print("fags = ", flags)
							print("bandwitdh = ", bandwidth)
							exit(1)

						# make new node from values we have and add to consensus
						self.add_node(name, identifier, flags, bandwidth)

						name = None
						flags = None
						bandwidth = None
					first_node = False

					name = tokens[1] # prefix, name, hash, hash, date, time, ip, port, ?
					identifier = tokens[2]
				elif prefix == "s": # flags for node
					flags = tokens[1:] # want all but the prfix
				elif prefix == "w": # bandwidth
					bandwidth_tokens = tokens[1].split(sep="=") # tokenize bandwidth and value
					bandwidth = int(bandwidth_tokens[1]) # convert to int
				elif prefix == "bandwidth-weights":
					self.set_weights(tokens[1:])
				else: # dont care about the others. TODO: include accept and reject ports for path selection?
					pass

				line = cf.readline()
	
	def set_weights(self, weights):
		for weight_value in weights:
			tokens = weight_value.split(sep="=")
			weight = tokens[0]
			value = int(tokens[1])
			self.weights[weight] = value

	def add_node(self, name, identifier, flags, bandwidth):
		self.nodes.append(node(name, identifier, flags, bandwidth))

	# get an exit node for the path
	def get_exit_node(self):
		exits = self.get_exit_nodes_for_path()
		return self.select_random_node(exits)

	# get a guard node for the path
	def get_guard_node(self):
		guards = self.get_guard_nodes_for_path()
		return self.select_random_node(guards)

	# get a middle node for the path
	def get_middle_node(self):
		middles = self.get_middle_nodes_for_path()
		return self.select_random_node(middles)

	# selects a random node based on the weights of the nodes
	# inspired by https://github.com/torps/torps/blob/9dce9adae4b0dbc9db4c75b2c350ac740f17ecd1/pathsim.py#L231
	def select_random_node(self, weighted_nodes):
		r = random.random()
		begin = 0
		end = len(weighted_nodes)-1
		mid = int((end+begin)/2)
		while True:
			if begin == mid or mid == end:
				return weighted_nodes[mid][0]
			if r <= weighted_nodes[mid][1]:
				end = mid
				mid = int((end+begin)/2)
			elif r > weighted_nodes[mid][1]:
				begin = mid
				mid = int((end+begin)/2)

		return weighted_nodes[0][0] # shouldnt reach this...

	# gets a list of exit (node, weight) pairs for path selection
	def get_exit_nodes_for_path(self):
		exits = self.get_exit_nodes()
		weighted_exits = self.weight_nodes(exits, 'e')
		return self.scale_weight_nodes(exits, weighted_exits, self.bwweight_scale)
		
	# gets a list of guard (node, weight) pairs for path selection
	def get_guard_nodes_for_path(self):
		guards = self.get_guard_nodes()
		weighted_guards = self.weight_nodes(guards, 'g')
		return self.scale_weight_nodes(guards, weighted_guards, self.bwweight_scale)

	# gets a list of middle (node, weight) pairs for path selection
	def get_middle_nodes_for_path(self):
		middles = self.get_middle_nodes()
		weighted_middles = self.weight_nodes(middles, 'm')
		return self.scale_weight_nodes(middles, weighted_middles, self.bwweight_scale)

	# weight each node provided s.t. its weight is the cumulative weight 
	# of previous nodes + node bandwidth * (bw weight / bwweight_scale) / total_bw
	# inspired from https://github.com/torps/torps/blob/9dce9adae4b0dbc9db4c75b2c350ac740f17ecd1/pathsim.py#L349
	# and https://github.com/torps/torps/blob/9dce9adae4b0dbc9db4c75b2c350ac740f17ecd1/pathsim.py#L361
	def scale_weight_nodes(self, nodes, weights, bwweight_scale):
		total_bw = 0
		for node in nodes:
			total_bw += node.bandwidth

		weighted_nodes = []
		cumulative_weight = 0
		for node in nodes:
			cumulative_weight += node.bandwidth * (weights[node] / bwweight_scale) / total_bw
			weighted_nodes.append((node, cumulative_weight))
		
		return weighted_nodes

	# create a dictionary of nodes and their weights provided in the consensus
	# position is either 'e', 'g'. 'm' for exit guard middle respectively
	def weight_nodes(self, nodes, position):
		node_weights = {}
		for node in nodes:
			weight = self.get_weight(node, position)
			node_weights[node] = weight
		return node_weights

	# get the weight of a node based on its position and flags
	def get_weight(self, node, position):
		if position == 'g': # guard node
			if node.is_guard() and node.is_exit():
				return self.weights['Wgd']
			elif node.is_guard():
				return self.weights['Wgg']
			else:
				return self.weights['Wgm']
		elif position == 'm': # middle node
			if node.is_guard() and node.is_exit():
				return self.weights['Wmd']
			elif node.is_guard():
				return self.weights['Wmg']
			elif node.is_exit():
				return self.weights['Wme']
			else:
				return self.weights['Wmm']
		elif position == 'e': # exit node
			if node.is_guard() and node.is_exit():
				return self.weights['Wed']
			elif node.is_guard():
				return self.weights['Weg']
			elif node.is_exit():
				return self.weights['Wee']
			else:
				return self.weights['Wem']
		else:
			return 10000

	# get all exit nodes from nodes list.
	# exit nodes must contain the Valid, Running, Fast, and Exit flags
	def get_exit_nodes(self):
		exits = []
		for node in self.nodes:
			if node.contains_flags(['Valid', 'Running', 'Fast', 'Exit']):
				exits.append(node)
		random.shuffle(exits)
		return exits

	# get all middle nodes from nodes list.
	# middle nodes must contain the Valid, Running, Fast flags
	def get_middle_nodes(self):
		middles = []
		for node in self.nodes:
			if node.contains_flags(['Valid', 'Running', 'Fast']):
				middles.append(node)
		random.shuffle(middles)
		return middles

	# get all guards nodes from nodes list.
	# guards nodes must contain the Valid, Running, Fast, and Guard flags
	def get_guard_nodes(self):
		guards = []
		for node in self.nodes:
			if node.contains_flags(['Valid', 'Running', 'Fast', 'Guard']):
				guards.append(node)
		random.shuffle(guards)
		return guards