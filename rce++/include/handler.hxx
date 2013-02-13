/*
 *    handler.hxx
 *
 *    This file is part of the RoboEarth Cloud Engine rce++ client.
 *
 *    This file was originally created for RoboEearth
 *    http://www.roboearth.org/
 *
 *    The research leading to these results has received funding from
 *    the European Union Seventh Framework Programme FP7/2007-2013 under
 *    grant agreement no248942 RoboEarth.
 *
 *    Copyright 2012 RoboEarth
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 *
 *     \author/s: Dominique Hunziker
 */

#ifndef HANDLER_HXX_
#define HANDLER_HXX_

#ifdef DEBUG
#include <iostream>
#endif

#include <websocketpp/roles/client.hpp>
#include <websocketpp/websocketpp.hpp>
#include "json_spirit/json_spirit_reader_template.h"
#include "json_spirit/json_spirit_writer_template.h"
#include "json_spirit/json_spirit_utils.h"
#include "types.hxx"

namespace rce
{

class ProtocolException: public std::runtime_error
{
	public:
		ProtocolException(const std::string &e) :
				std::runtime_error::runtime_error(e)
		{
		}
};

template<class Client>
class Protocol_impl: public websocketpp::client::handler
{
	private:
		typedef std::pair<typename Client::String, typename Client::Binary*> _BinaryIn_t;
		typedef std::vector<_BinaryIn_t> _BinaryInVector_t;
		typedef std::pair<typename Client::Object, _BinaryInVector_t> _PendingMessage_t;
		typedef std::vector<_PendingMessage_t> _PendingMessageVector_t;
		typedef std::vector<typename Client::String> _BinaryOutVector_t;
		typedef std::pair<std::string, typename Client::Interface_t*> _InterfaceRef_t;
		typedef std::vector<_InterfaceRef_t> _InterfaceRefVector_t;

	public:
		Protocol_impl(typename Client::ClientPtr_t client) :
				_client(client)
		{
		}

		void on_message(connection_ptr con, message_ptr msg);
		void on_fail(connection_ptr con);
		void on_open(connection_ptr con);
		void on_close(connection_ptr con);

		void registerInterface(const typename Client::String &tag,
				typename Client::Interface_t* interface);
		void unregisterInterface(const typename Client::String &tag,
				typename Client::Interface_t* interface);

		void send(const typename Client::String &type,
				const typename Client::Object &data);
		void send(const typename Client::String &tag,
				const typename Client::String &type,
				const typename Client::Value &msg,
				const typename Client::String &msgID);

	private:
		void onConnect();

		void processMessage(const std::string &msg);
		void processMessage(const typename Client::Object &msg);
		void processBinary(const std::string &msg);

		void processData(const typename Client::Object &data);
		void processStatus(const typename Client::String &data);
		void processError(const typename Client::String &data);

		void send(const std::string &message, bool binary);

		connection_ptr _con; // Pointer to session object of websocketpp
		_PendingMessageVector_t _pending;

		typename Client::ClientPtr_t _client;

		_InterfaceRefVector_t _interfaces;
};

///////////////////////////////////////////////////////////////////////////////
/////  Implementation
///////////////////////////////////////////////////////////////////////////////

///////////////////////////////////////////////////////////////////////////////
////	Protocol_impl
template<class Client>
void Protocol_impl<Client>::on_message(connection_ptr con, message_ptr msg)
{
	switch (msg->get_opcode())
	{
	case websocketpp::frame::opcode::TEXT:
		this->processMessage(msg->get_payload());
		break;

	case websocketpp::frame::opcode::BINARY:
		this->processBinary(msg->get_payload());
		break;

	default:
		throw ProtocolException(
				"Received message from Cloud Engine has invalid type (websocket).");
	}
}

template<class Client>
void Protocol_impl<Client>::on_fail(connection_ptr con)
{
	throw ProtocolException(
			"Connection to Cloud Engine failed: " + con->get_fail_reason());
}

template<class Client>
void Protocol_impl<Client>::on_open(connection_ptr con)
{
	if (_con != NULL)
		throw ProtocolException(
				"Can not register connection. There is already a connection registered.");

	_con = con;

	this->onConnect();
}

template<class Client>
void Protocol_impl<Client>::on_close(connection_ptr con)
{
	if (_con == NULL)
		throw ProtocolException(
				"Can not unregister connection. There is no connection registered.");

	_con = connection_ptr();
}

template<class Client>
void Protocol_impl<Client>::registerInterface(
		const typename Client::String &tag,
		typename Client::Interface_t* interface)
{
	typename _InterfaceRefVector_t::iterator it;

	for (it = _interfaces.begin(); it < _interfaces.end(); it++)
		if (it->first == tag && it->second == interface)
			throw ProtocolException(
					"Can not register Interface. It is already registered.");

	_interfaces.push_back(_InterfaceRef_t(tag, interface));
}

template<class Client>
void Protocol_impl<Client>::unregisterInterface(
		const typename Client::String &tag,
		typename Client::Interface_t* interface)
{
	typename _InterfaceRefVector_t::iterator it;

	for (it = _interfaces.begin(); it < _interfaces.end(); it++)
		if (it->first == tag && it->second == interface)
			break;

	if (it != _interfaces.end())
		_interfaces.erase(it);
	else
		throw ProtocolException(
				"Can not unregister Interface. It is not registered.");
}

template<class Client>
void Protocol_impl<Client>::send(const typename Client::String &type,
		const typename Client::Object &data)
{
	typename Client::Object message;
	Client::Config_t::add(message, "type", type);
	Client::Config_t::add(message, "data", data);

	_BinaryOutVector_t binaries = _BinaryOutVector_t();
	typename _BinaryOutVector_t::iterator it;

	this->send(
			json_spirit::write_string(typename Client::Value(message), binaries,
					false), false);

	for (it = binaries.begin(); it != binaries.end(); ++it)
		this->send(*it, true);
}

template<class Client>
void Protocol_impl<Client>::send(const typename Client::String &tag,
		const typename Client::String &type, const typename Client::Value &msg,
		const typename Client::String &msgID)
{
	typename Client::Object data;
	Client::Config_t::add(data, "iTag", tag);
	Client::Config_t::add(data, "type", type);
	Client::Config_t::add(data, "msgID", msgID);
	Client::Config_t::add(data, "msg", msg);

	send(RCE_DATA_MESSAGE, data);
}

template<class Client>
void Protocol_impl<Client>::processMessage(const std::string &msg)
{
	typename Client::Value messageValue;
	_BinaryInVector_t binaries;

	json_spirit::read_string_or_throw(msg, messageValue, binaries);

	if (messageValue.type() != json_spirit::obj_type)
		throw ProtocolException(
				"Received a message from Cloud Engine with invalid JSON format.");

	typename Client::Object message = messageValue.get_obj();

	if (!binaries.empty())
		_pending.push_back(_PendingMessage_t(message, binaries));
	else
		this->processMessage(message);
}

template<class Client>
void Protocol_impl<Client>::processBinary(const std::string &msg)
{
	if (msg.length() < 32)
		throw ProtocolException(
				"Received a binary message with invalid header.");

	std::string uid = msg.substr(0, 32);
	std::string binary = msg.substr(32);

	typename _PendingMessageVector_t::iterator msgIt;
	typename _BinaryInVector_t::iterator binIt;

	for (msgIt = _pending.begin(); msgIt != _pending.end(); ++msgIt)
		for (binIt = msgIt->second.begin(); binIt != msgIt->second.end();
				++binIt)
			if (binIt->first == uid)
				goto match;

	match:

	if (msgIt != _pending.end() && binIt != msgIt->second.end())
	{
		binIt->second->set_data(binary);
		msgIt->second.erase(binIt);

		if (msgIt->second.empty())
		{
			this->processMessage(msgIt->first);
			_pending.erase(msgIt);
		}
	}
	else
		throw ProtocolException("Received binary message was not expected.");
}

template<class Client>
void Protocol_impl<Client>::processMessage(const typename Client::Object &msg)
{
	typename Client::Value type = json_spirit::find_value<
			typename Client::Object, typename Client::String>(msg, "type");
	typename Client::Value data = json_spirit::find_value<
			typename Client::Object, typename Client::String>(msg, "data");

	if (type.type() != json_spirit::str_type)
		throw ProtocolException(
				"Received a message from Cloud Engine with invalid type for field 'type'.");

	typename Client::String dataType = type.get_str();

	if (dataType == RCE_DATA_MESSAGE)
	{
		if (data.type() != json_spirit::obj_type)
			throw ProtocolException(
					"Received a message from Cloud Engine with invalid type for field 'data'.");

		this->processData(data.get_obj());
	}
	else if (dataType == RCE_STATUS)
	{
		if (data.type() != json_spirit::str_type)
			throw ProtocolException(
					"Received a message from Cloud Engine with invalid type for field 'data'.");

		this->processStatus(data.get_str());
	}
	else if (dataType == RCE_ERROR)
	{
		if (data.type() != json_spirit::str_type)
			throw ProtocolException(
					"Received a message from Cloud Engine with invalid type for field 'data'.");

		this->processError(data.get_str());
	}
	else
		throw ProtocolException(
				"Received a message from Cloud Engine with invalid type: "
						+ dataType);
}

template<class Client>
void Protocol_impl<Client>::processData(const typename Client::Object &data)
{
	typename Client::Value tag = json_spirit::find_value<
			typename Client::Object, typename Client::String>(data, "iTag");
	typename Client::Value type = json_spirit::find_value<
			typename Client::Object, typename Client::String>(data, "type");
	typename Client::Value msgID = json_spirit::find_value<
			typename Client::Object, typename Client::String>(data, "msgID");
	typename Client::Value msg = json_spirit::find_value<
			typename Client::Object, typename Client::String>(data, "msg");

#ifdef DEBUG
	if (tag.type() != json_spirit::str_type)
	std::cout << "Message's interface tag is not a valid string." << std::endl;

	if (type.type() != json_spirit::str_type)
	std::cout << "Message type is not a valid string." << std::endl;

	if (msgID.type() != json_spirit::str_type)
	std::cout << "Message ID is not a valid string." << std::endl;

	if (msg.type() != json_spirit::obj_type && msg.type() != json_spirit::bin_type)
	std::cout << "Message is neither a valid binary nor a valid object." << std::endl;
#endif

	if (tag.type() != json_spirit::str_type
			|| type.type() != json_spirit::str_type
			|| msgID.type() != json_spirit::str_type
			|| (msg.type() != json_spirit::obj_type
					&& msg.type() != json_spirit::bin_type))
		throw ProtocolException(
				"Received a message from Robot Manager with invalid format.");

	typename Client::String iTag = tag.get_str();

	typename _InterfaceRefVector_t::iterator it;

	for (it = _interfaces.begin(); it < _interfaces.end(); it++)
		if (it->first == iTag)
			it->second->receive(type.get_str(), msg, msgID.get_str());
}

template<class Client>
void Protocol_impl<Client>::processStatus(const typename Client::String &data)
{
	std::cout << data << std::endl;
}

template<class Client>
void Protocol_impl<Client>::processError(const typename Client::String &data)
{
	std::cout << data << std::endl;
}

template<class Client>
void Protocol_impl<Client>::onConnect()
{
#ifdef DEBUG
	std::cout << "Connection established." << std::endl;
#endif

	if (_client.get())
		_client->connected();
}

template<class Client>
void Protocol_impl<Client>::send(const std::string &message, bool binary)
{
#ifdef DEBUG
	if (!binary)
	std::cout << "Send message: " << message << std::endl;
#endif
	websocketpp::message::data_ptr msg = _con->get_data_message();

	if (binary)
		msg->reset(websocketpp::frame::opcode::BINARY);
	else
		msg->reset(websocketpp::frame::opcode::TEXT);

	msg->set_payload(message);
	_con->send(msg);
}

} /* namespace rce */

#endif /* CLIENT_HXX_ */
